#!/usr/bin/env python3
"""EVERY PREDICTION THIS DESK MAKES IS SCORED, AND A MODEL THAT CANNOT BEAT ITS BASELINE IS NOT
A MODEL.

THE DEFECT THIS ENDS. The desk predicts constantly. The gauntlet predicts that a certified sleeve
will survive forward. The allocator predicts `expected_gain_per_day`. The decay engine predicts
that an alpha is decaying. The execution twin predicts what a fill would have been. Every one of
those is a falsifiable claim about the future, every one of them is written to an artifact with a
timestamp, and exactly ONE of them -- the engineering/research forecast register scored by
`libs/self_improvement/forecast_calibration` -- has ever been checked against what actually
happened.

A prediction nobody scores cannot improve. It cannot even be known to be wrong. So the desk has a
20-module self-improvement package (drift detection, decay, meta-learning, weight proposals,
ensembles, kill switches) that is structurally advisory by design -- it proposes and never
applies -- sitting on top of predictors whose accuracy has never been measured. Advice computed
from an unscored model is not self-improvement; it is opinion with a changelog.

WHAT THIS DOES, and the order matters:

    1. REGISTER      every predictor: what it predicts, where the claim lands, where the OUTCOME
                     lands, and how the two are joined. A predictor missing from here is a
                     prediction nobody is scoring, which is the defect above.
    2. SCORE         skill against a NAMED BASELINE -- Brier skill vs the base rate for
                     probabilities, MAE skill vs persistence for real numbers. Never raw accuracy:
                     "we were right 78% of the time" is meaningless without knowing that always
                     saying yes would have been right 80% of the time.
    3. CHALLENGE     refit on the newest window, score the challenger on data the champion also
                     did not see, and promote ONLY on measured improvement.
    4. TRACK         append every cycle's skill to a ledger, so "are our predictions getting
                     better" is a time series somebody can read rather than a claim somebody makes.

SKILL, NOT ACCURACY, AND A NAMED BASELINE FOR EACH. A model is only worth its compute if it beats
the cheapest thing that would have worked. `skill = 1 - loss(model) / loss(baseline)`: positive
means the model earns its place, zero means the baseline was free and just as good, negative means
the desk is paying to be worse than a constant.

UNMEASURED IS NOT A PASS (L1.28a). A predictor whose claims are never written down, or whose
outcomes never arrive, comes back UNMEASURED and this exits non-zero on it. "No skill number" and
"skill was fine" are different states and only one of them is evidence. On a host with no live
artifacts -- this container, a fresh clone -- every predictor is UNMEASURED and that is the
correct, loud answer rather than a green report about data that is not here.

PROMOTION IS EARNED IN THE SAME CURRENCY AS EVERYTHING ELSE. A challenger replaces a champion only
when it improves out-of-sample skill by more than `MIN_SKILL_GAIN`, on at least `MIN_N` resolved
predictions. It never replaces on in-sample fit, never on a tie, and never because it is newer.

    python desks/mt5/research/model_self_improvement.py [--json]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REPORT = BASE / "reports" / "MODEL_SELF_IMPROVEMENT.json"
TRACK = BASE / "data" / "model_skill_track.jsonl"
#: Where a seat's claims meet their verdicts: every hypothesis the compiler admitted carries the
#: seat's name as its source, and the gauntlet's fate is the outcome.
GRAPH = BASE / "data" / "hypothesis_graph.jsonl"

#: THE LLM SEATS ARE PREDICTORS (2026-09-09, inventory I13). A seat that donates a hypothesis is
#: claiming it will survive the gauntlet; the graph records whether it did. Each seat is
#: registered once per LANE -- macro and scalp -- so the per-lane posterior follows the same
#: MIN_N gate as every other predictor, and a seat that is skilled on daily mechanisms and
#: worthless on M5 ones is reported as exactly that rather than as one blended number.
#: Names mirror `miner_candidate_compiler.SEAT_SOURCES` and the seats' own `_donate` writers.
SEATS: tuple[tuple[str, str], ...] = (
    ("deepseek", "libs/ops/deepseek_cycle.py"),
    ("kimi_k3_deep_forest", "scripts/kimi_hunter.py"),
)
LANES: tuple[str, ...] = ("macro", "scalp")
#: DECLARED lane rule. The scalp lane is the M1/M5/M15 lane (`mt5desk.scalp_families`
#: SWEPT_TIMEFRAMES) and its families are the scalp expansion's; everything else the seats
#: donate is a session-or-slower mechanism, which is the macro lane.
SCALP_TIMEFRAMES: tuple[str, ...] = ("M1", "M5", "M15")

#: (predicted, actual) in TIME ORDER. The order is load-bearing: `_split` is positional, so a
#: shuffled series would train a challenger on outcomes resolved after the ones it is graded on.
Pairs = list[tuple[float, float]]

#: Resolved predictions below which no skill number is reported. A skill score on four
#: observations is noise wearing a decimal point, and the desk has been burned by exactly that
#: shape before -- a coverage counter that grew with test volume and read as evidence.
MIN_N = 20

#: Out-of-sample skill a challenger must ADD before it may take the champion's place. Not zero:
#: at zero, every refit that moved a decimal would promote, the champion would change every hour,
#: and nothing would ever accumulate enough forward evidence to be judged at all. Churn is a cost
#: even when each individual swap looks free.
MIN_SKILL_GAIN = 0.02


@dataclass(frozen=True)
class Predictor:
    """One falsifiable claim the desk makes, and how to find out whether it came true.

    `claims` and `outcomes` are callables rather than paths because the join is never uniform:
    the forecast register keeps the claim and the outcome on the SAME row, the gauntlet writes its
    claim in one artifact and its outcome in a forward ledger written weeks later, and the
    execution twin computes both in one pass. What they must all produce is the same pair --
    (predicted, actual) -- because that pair is the only thing a skill score can be computed from.
    """
    name: str
    predicts: str
    kind: str                          # "probability" or "real"
    baseline: str                      # what the model has to beat, in words
    pairs: Callable[[], list[tuple[float, float]]]
    owner: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------- skill


def brier_skill(pairs: list[tuple[float, float]]) -> tuple[float | None, str]:
    """Brier skill against the BASE RATE, which is the honest baseline for a probability.

    Raw Brier score is uninterpretable on its own: 0.12 is excellent for a coin-flip event and
    terrible for one that happens 97% of the time. Against the base rate, positive means the
    forecast carried information the unconditional frequency did not.
    """
    if len(pairs) < MIN_N:
        return None, f"only {len(pairs)} resolved prediction(s), below MIN_N={MIN_N}"
    ps = [p for p, _ in pairs]
    ys = [y for _, y in pairs]
    base = sum(ys) / len(ys)
    loss = sum((p - y) ** 2 for p, y in zip(ps, ys, strict=True)) / len(pairs)
    ref = sum((base - y) ** 2 for y in ys) / len(ys)
    if ref <= 0:
        return None, ("every outcome was identical, so the base rate is a perfect predictor and "
                      "no skill is measurable -- this is UNMEASURED, not skill of zero")
    return 1.0 - loss / ref, f"n={len(pairs)}, base rate {base:.3f}"


def mae_skill(pairs: list[tuple[float, float]]) -> tuple[float | None, str]:
    """MAE skill against PERSISTENCE -- predicting that the next value equals the last one.

    Persistence rather than the mean, deliberately. For a series with any autocorrelation the mean
    is a straw man: beating it proves nothing, and a model that beats the mean while losing to
    "assume tomorrow is like today" is a model the desk should switch off.
    """
    if len(pairs) < MIN_N:
        return None, f"only {len(pairs)} resolved prediction(s), below MIN_N={MIN_N}"
    ys = [y for _, y in pairs]
    loss = sum(abs(p - y) for p, y in pairs) / len(pairs)
    ref = sum(abs(ys[i - 1] - ys[i]) for i in range(1, len(ys))) / max(1, len(ys) - 1)
    if ref <= 0:
        return None, ("the series never moved, so persistence is exact and no skill is "
                      "measurable -- UNMEASURED, not skill of zero")
    return 1.0 - loss / ref, f"n={len(pairs)}, persistence MAE {ref:.6g}"


def score(p: Predictor) -> dict[str, Any]:
    """One predictor's verdict. SKILLED, NO_SKILL, or UNMEASURED -- and the last is not a pass."""
    try:
        pairs = [(float(a), float(b)) for a, b in p.pairs()
                 if math.isfinite(float(a)) and math.isfinite(float(b))]
    except Exception as exc:
        # THE TAGS SURVIVE THE FAILED JOIN. A predictor whose claims cannot reach their outcomes
        # is still a predictor of a named lane; dropping `tags` here would make the per-lane
        # scoreboard lose exactly the rows it most needs to show as unscored.
        return {"name": p.name, "status": "UNMEASURED", "skill": None, "n": 0,
                "why": f"claims could not be joined to outcomes ({type(exc).__name__}: {exc})",
                "predicts": p.predicts, "baseline": p.baseline,
                "kind": p.kind, "owner": p.owner, "tags": list(p.tags)}
    fn = brier_skill if p.kind == "probability" else mae_skill
    skill, why = fn(pairs)
    status = "UNMEASURED" if skill is None else ("SKILLED" if skill > 0 else "NO_SKILL")
    return {"name": p.name, "status": status,
            "skill": None if skill is None else round(skill, 6),
            "n": len(pairs), "why": why, "predicts": p.predicts, "baseline": p.baseline,
            "kind": p.kind, "owner": p.owner, "tags": list(p.tags)}


def promote(champion: dict[str, Any], challenger: dict[str, Any]) -> tuple[bool, str]:
    """Does the challenger replace the champion? Only on MEASURED out-of-sample improvement.

    THE THREE REFUSALS ARE THE WHOLE VALUE. A challenger does not win because it is newer, because
    it fits the training window better, or because the champion happens to be UNMEASURED this
    cycle -- an unmeasured champion is a champion nobody has scored, which is a reason to score it
    rather than a reason to replace it with something else nobody has scored either.
    """
    cs, hs = challenger.get("skill"), champion.get("skill")
    if cs is None:
        return False, "challenger is UNMEASURED -- it has not earned a comparison, let alone a seat"
    if hs is None:
        return False, ("champion is UNMEASURED, so there is no measured improvement to be had. "
                       "Score the champion first; swapping one unscored model for another is "
                       "churn that looks like progress")
    if challenger.get("n", 0) < MIN_N:
        return False, f"challenger scored on {challenger.get('n', 0)} < MIN_N={MIN_N} outcomes"
    gain = cs - hs
    if gain <= MIN_SKILL_GAIN:
        return False, (f"skill gain {gain:+.4f} does not clear MIN_SKILL_GAIN={MIN_SKILL_GAIN}; "
                       f"promoting on a smaller move buys churn, not accuracy")
    return True, f"out-of-sample skill {hs:.4f} -> {cs:.4f} ({gain:+.4f})"


# ---------------------------------------------------------------- challengers
#
# A CHALLENGER IS A CHEAP REPAIR THE DESK COULD APPLY TO ITS OWN FORECAST, and each one is a
# hypothesis about WHY the champion is wrong. Fitted on the earlier half of the record and scored
# on the later half, so a challenger can never be trained on an outcome it is graded against.
#
# MEASURED 2026-09-05, and the result is the reason this machinery is worth its lines. The
# champion -- the desk's raw probability forecast over 537 resolved claims -- scores Brier skill
# -0.177 against its own base rate: it is worse than a constant. Both obvious repairs were then
# refused by the gate below, because both are WORSE out of sample:
#
#     champion (raw forecast)                 -0.8805
#     per-kind base rate                      -1.5474
#     per-kind bias shift                     -3.2276
#
# The miscalibration is real and it is NOT STATIONARY: the bias learned on the first half does not
# survive into the second, so correcting for yesterday's overconfidence makes tomorrow worse. That
# is a finding, not a failure of the loop -- the loop's job was to stop a plausible repair from
# being deployed on the strength of an in-sample fit, and it did.


def _split(pairs: Pairs) -> tuple[Pairs, Pairs]:
    """Earlier half to fit on, later half to be judged on. Never shuffled, never overlapping."""
    cut = len(pairs) // 2
    return pairs[:cut], pairs[cut:]


def _brier(pairs: Pairs) -> float:
    return float(sum((p - y) ** 2 for p, y in pairs)) / len(pairs)


def _skill_of(loss: float, pairs: Pairs) -> float | None:
    base = float(sum(y for _, y in pairs)) / len(pairs)
    ref = sum((base - y) ** 2 for _, y in pairs) / len(pairs)
    return None if ref <= 0 else 1.0 - loss / ref


def _chal_base_rate(train: Pairs, test: Pairs) -> float:
    """Ignore the forecast entirely and quote the historical frequency.

    The strongest possible statement of "the model adds nothing": if this wins, the desk should
    stop forecasting and publish a constant.
    """
    rate = float(sum(y for _, y in train)) / len(train)
    return float(sum((rate - y) ** 2 for _, y in test)) / len(test)


def _chal_bias_shift(train: Pairs, test: Pairs) -> float:
    """Keep the forecast's ordering, subtract its measured average overconfidence."""
    shift = (float(sum(y for _, y in train)) - float(sum(p for p, _ in train))) / len(train)
    return float(sum((min(1.0, max(0.0, p + shift)) - y) ** 2 for p, y in test)) / len(test)


def _chal_shrink_to_base(train: Pairs, test: Pairs) -> float:
    """Pull every forecast halfway to the base rate.

    The repair for overconfidence that does NOT assume the bias is stable in direction -- it only
    assumes the forecast is too extreme, which is the one thing the calibration table said
    unambiguously (79% of forecasts sit in 0.3-0.7 and the 0.6-0.7 bin came true 6% of the time).
    """
    rate = float(sum(y for _, y in train)) / len(train)
    return float(sum(((0.5 * p + 0.5 * rate) - y) ** 2 for p, y in test)) / len(test)


CHALLENGERS: dict[str, Callable[[Pairs, Pairs], float]] = {
    "base_rate": _chal_base_rate,
    "bias_shift": _chal_bias_shift,
    "shrink_to_base": _chal_shrink_to_base,
}


def challenge(p: Predictor) -> dict[str, Any]:
    """Walk-forward: can any cheap repair beat the champion on data neither of them saw?"""
    if p.kind != "probability":
        return {"status": "NOT_APPLICABLE",
                "why": "the challenger set is calibration repairs, which are defined for "
                       "probabilities; a real-valued predictor needs its own challengers"}
    pairs = p.pairs()
    train, test = _split(pairs)
    if len(train) < MIN_N or len(test) < MIN_N:
        return {"status": "UNMEASURED",
                "why": f"walk-forward needs {MIN_N} on each side; got {len(train)}/{len(test)}"}
    champ = {"skill": _skill_of(_brier(test), test), "n": len(test)}
    rows = []
    for name, fn in CHALLENGERS.items():
        sk = _skill_of(fn(train, test), test)
        row = {"name": name, "skill": None if sk is None else round(sk, 6), "n": len(test)}
        row["promote"], row["why"] = promote(champ, row)
        rows.append(row)
    winner = next((r for r in rows if r["promote"]), None)
    return {
        "status": "PROMOTE" if winner else "CHAMPION_HELD",
        "champion_skill": None if champ["skill"] is None else round(champ["skill"], 6),
        "train_n": len(train), "test_n": len(test),
        "challengers": rows,
        "winner": winner["name"] if winner else None,
        "rule": (f"a challenger takes the seat only on out-of-sample skill gain > "
                 f"{MIN_SKILL_GAIN} over at least {MIN_N} outcomes -- never on in-sample fit, "
                 f"never on a tie, never for being newer"),
    }


# ---------------------------------------------------------------- the registry


def _forecast_register_pairs() -> list[tuple[float, float]]:
    """The desk's own probability forecasts, joined to their resolutions, OLDEST FIRST.

    THE ORDER IS PART OF THE CONTRACT for every `pairs` callable in the registry, because the
    walk-forward split below is a split on POSITION. A shuffled series would let a challenger be
    trained on outcomes that resolved after the ones it is scored on -- lookahead, dressed as an
    out-of-sample test, in the one place on the desk built to catch exactly that.
    """
    p = ROOT / "data" / "forecast_log.json"
    if not p.exists():
        return []
    doc = json.loads(p.read_text("utf-8"))
    rows = doc.get("forecasts", doc) if isinstance(doc, dict) else {}
    got = []
    for row in (rows.values() if isinstance(rows, dict) else rows):
        if not isinstance(row, dict) or not row.get("resolved"):
            continue
        prob, outcome = row.get("p"), row.get("outcome")
        if prob is None or outcome is None:
            continue
        got.append((str(row.get("resolved_at") or row.get("updated") or ""),
                    float(prob), float(outcome)))
    got.sort(key=lambda r: r[0])
    return [(p, y) for _at, p, y in got]


def _survivor_forward_pairs() -> list[tuple[float, float]]:
    """THE DESK'S MOST EXPENSIVE PREDICTION: the gauntlet says a sleeve survives; forward says.

    Every certificate is a claim that an edge persists out of sample. The forward clocks then
    record what the sleeve actually did. Nothing has ever joined the two, which means the desk has
    never measured whether its own ten-gate certification PREDICTS anything -- the single number
    that would tell it whether the gauntlet is worth what it costs.

    Joined on the run key. The certificate's expected edge is the claim; the forward ledger's
    realised edge over the same measure is the outcome.
    """
    cert = BASE / "reports" / "UNIVERSAL_SURVIVORS.json"
    if not cert.exists():
        cert = BASE / "data" / "UNIVERSAL_SURVIVORS.canon.json"
    if not cert.exists():
        return []
    doc = json.loads(cert.read_text("utf-8"))
    survivors = doc.get("survivors") or {}
    out: list[tuple[float, float]] = []
    for key, row in survivors.items():
        if not isinstance(row, dict):
            continue
        claim = row.get("expected_edge_r", row.get("edge_r"))
        led = BASE / "reports" / "shadow" / f"ledger_{key}.json"
        if claim is None or not led.exists():
            continue
        try:
            fwd = json.loads(led.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        actual = fwd.get("realised_edge_r", fwd.get("edge_r"))
        if actual is None:
            continue
        out.append((float(claim), float(actual)))
    return out


def _allocator_gain_pairs() -> list[tuple[float, float]]:
    """`expected_gain_per_day` against the gain that actually arrived.

    The allocator's entire job is this number. It has never been scored against realisation, so
    the desk sizes capital on a forecast whose track record is unknown.
    """
    p = BASE / "reports" / "ALLOCATOR_STACK.json"
    if not p.exists():
        return []
    doc = json.loads(p.read_text("utf-8"))
    hist = doc.get("gain_history") or []
    return [(float(r["expected"]), float(r["realised"])) for r in hist
            if isinstance(r, dict) and r.get("expected") is not None
            and r.get("realised") is not None]


def _seat_of(source: Any) -> str | None:
    """The seat named by a graph row's source (`deepseek`, or `miner:deepseek` once compiled)."""
    text = str(source or "")
    head, _, tail = text.partition(":")
    names = {s for s, _ in SEATS}
    if head in names:
        return head
    seat = tail.split(":")[0]
    return seat if head == "miner" and seat in names else None


_SCALP_FAMILIES: dict[str, frozenset[str]] = {}


def _scalp_families() -> frozenset[str]:
    """The scalp expansion's family names, read once from the code that defines them; empty
    when that code cannot be imported here, in which case only the timeframe rule applies."""
    if "names" not in _SCALP_FAMILIES:
        try:
            if str(BASE) not in sys.path:
                sys.path.insert(0, str(BASE))
            from mt5desk.scalp_families import _family_names
            _SCALP_FAMILIES["names"] = frozenset(_family_names())
        except Exception:
            _SCALP_FAMILIES["names"] = frozenset()
    return _SCALP_FAMILIES["names"]


def _lane_of(row: dict[str, Any]) -> str:
    params = row.get("params") if isinstance(row.get("params"), dict) else {}
    tf = str(params.get("timeframe") or params.get("tf") or "").upper()
    if tf in SCALP_TIMEFRAMES:
        return "scalp"
    fam = str(row.get("family") or "")
    if fam.startswith("scalp") or fam in _scalp_families():
        return "scalp"
    return "macro"


def _stated_probability(row: dict[str, Any]) -> float | None:
    """The P(survive) the seat stated on this hypothesis, if it stated one at all."""
    for key in ("confidence", "p_survive", "p"):
        v = row.get(key)
        if isinstance(v, (int, float)) and not isinstance(v, bool) and 0.0 <= float(v) <= 1.0:
            return float(v)
    return None


def _seat_pairs(seat: str, lane: str) -> Callable[[], list[tuple[float, float]]]:
    """(stated P(survive), 1 if CERTIFIED else 0) for the seat's judged hypotheses in `lane`,
    OLDEST FIRST. Raises with the missing input named when the pair cannot be formed, so the
    scoreboard reads UNMEASURED with the reason rather than n=0."""

    def pairs() -> list[tuple[float, float]]:
        if not GRAPH.exists():
            raise FileNotFoundError(
                f"{GRAPH.name} absent -- no hypothesis has been registered on this host, so "
                f"the {seat} seat's claims cannot be joined to a verdict")
        latest: dict[str, dict[str, Any]] = {}
        for line in GRAPH.read_text("utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict) and row.get("id") and _seat_of(row.get("source")) == seat:
                latest[str(row["id"])] = row               # appended in time order: last wins
        if not latest:
            raise LookupError(
                f"no hypothesis_graph node names source miner:{seat} -- the seat has donated "
                f"nothing the compiler admitted, or the compiler ran before the seat did")
        in_lane = [r for r in latest.values() if _lane_of(r) == lane]
        if not in_lane:
            raise LookupError(
                f"{seat}/{lane}: none of the seat's {len(latest)} hypothesis(es) is in the "
                f"{lane} lane (lane by params.timeframe in {SCALP_TIMEFRAMES} or a scalp family)")
        judged = sorted((r for r in in_lane if r.get("fate") in ("CERTIFIED", "FAILED", "BURIED")),
                        key=lambda r: str(r.get("at") or ""))
        out: list[tuple[float, float]] = []
        for r in judged:
            p = _stated_probability(r)
            if p is not None:
                out.append((p, 1.0 if r.get("fate") == "CERTIFIED" else 0.0))
        if not out:
            certified = sum(1 for r in judged if r.get("fate") == "CERTIFIED")
            raise LookupError(
                f"{seat}/{lane}: {len(in_lane)} donated hypothesis(es), {len(judged)} judged "
                f"({certified} certified, {len(judged) - certified} failed), none states "
                f"P(survive) -- the seat's donation contract carries no confidence and "
                f"hypothesis_graph.Node has no field for one, so Brier skill cannot be scored")
        return out

    return pairs


def _seat_predictors() -> tuple[Predictor, ...]:
    return tuple(
        Predictor(
            name=f"seat_{seat}[{lane}]",
            predicts=(f"whether a hypothesis the {seat} seat donates in the {lane} lane "
                      f"survives the gauntlet"),
            kind="probability",
            baseline="the base rate of the seat's judged hypotheses in this lane certifying",
            pairs=_seat_pairs(seat, lane),
            owner=owner,
            tags=("llm_seat", lane),
        )
        for seat, owner in SEATS for lane in LANES)


REGISTRY: tuple[Predictor, ...] = (
    Predictor(
        name="research_forecast",
        predicts="whether a named engineering or research claim resolves true",
        kind="probability",
        baseline="the base rate of resolved claims coming true",
        pairs=_forecast_register_pairs,
        owner="libs/self_improvement/forecast_calibration.py",
        tags=("governance", "calibration"),
    ),
    Predictor(
        name="gauntlet_survival",
        predicts="the forward edge of a certificate that passed all ten gates",
        kind="real",
        baseline="persistence -- assume the next sleeve does what the last one did",
        pairs=_survivor_forward_pairs,
        owner="desks/mt5/research/shadow_admission.py",
        tags=("gauntlet", "certification", "forward"),
    ),
    Predictor(
        name="allocator_expected_gain",
        predicts="expected_gain_per_day for the allocated book",
        kind="real",
        baseline="persistence -- assume today's gain equals yesterday's",
        pairs=_allocator_gain_pairs,
        owner="desks/mt5/research/pf_allocator.py",
        tags=("capital", "allocation"),
    ),
    *_seat_predictors(),
)


# ---------------------------------------------------------------- the loop


def run() -> dict[str, Any]:
    rows = [score(p) for p in REGISTRY]
    measured = [r for r in rows if r["skill"] is not None]
    unmeasured = [r for r in rows if r["skill"] is None]
    no_skill = [r for r in measured if r["status"] == "NO_SKILL"]
    status = "OK"
    problems: list[str] = []
    if unmeasured:
        status = "UNMEASURED"
        problems.append(
            f"{len(unmeasured)} of {len(rows)} predictor(s) make claims nobody scores: "
            f"{[r['name'] for r in unmeasured]}. A prediction that is never checked cannot "
            f"improve and cannot be known to be wrong -- this is the absence of evidence, not "
            f"evidence of accuracy (L1.28a).")
    if no_skill:
        status = "BREACH"
        problems.append(
            f"{len(no_skill)} predictor(s) LOSE to their own baseline: "
            f"{[(r['name'], r['skill']) for r in no_skill]}. The desk is paying compute to be "
            f"worse than a constant. Retire the model or fix it; do not keep reporting it.")
    return {
        "at": datetime.now(UTC).isoformat(),
        "status": status,
        "predictors": rows,
        "measured": len(measured),
        "unmeasured": len(unmeasured),
        "min_n": MIN_N,
        "min_skill_gain": MIN_SKILL_GAIN,
        "problems": problems,
        "law": ("skill is measured against a NAMED baseline, never as raw accuracy; UNMEASURED "
                "is not a pass; a challenger is promoted only on out-of-sample improvement"),
    }


def track(doc: dict[str, Any]) -> int:
    """Append this cycle's skill numbers so improvement over time is a SERIES, not a claim.

    One line per cycle per measured predictor. Without this the desk can say "our models are
    getting better" and have no way to be contradicted, which is the same shape as every other
    unfalsifiable claim this repo spends its time fencing out.
    """
    rows = [r for r in doc["predictors"] if r["skill"] is not None]
    if not rows:
        return 0
    TRACK.parent.mkdir(parents=True, exist_ok=True)
    with TRACK.open("a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps({"at": doc["at"], "name": r["name"], "skill": r["skill"],
                                 "n": r["n"], "status": r["status"]}, ensure_ascii=False) + "\n")
    return len(rows)


def trend(name: str, window: int = 20) -> dict[str, Any]:
    """Is this predictor actually getting better? The answer, or an honest refusal to give one."""
    if not TRACK.exists():
        return {"name": name, "trend": None, "why": "no skill track on this host yet"}
    pts = []
    for line in TRACK.read_text("utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("name") == name and row.get("skill") is not None:
            pts.append(float(row["skill"]))
    if len(pts) < 4:
        return {"name": name, "trend": None,
                "why": f"{len(pts)} scored cycle(s); a trend on fewer than 4 is a line through "
                       f"noise"}
    recent, older = pts[-window:], pts[:-window] or pts[:len(pts) // 2]
    return {"name": name, "trend": round(sum(recent) / len(recent) - sum(older) / len(older), 6),
            "cycles": len(pts), "latest": pts[-1]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    doc = run()
    doc["tracked"] = track(doc)
    doc["trends"] = [trend(p.name) for p in REGISTRY]
    try:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    except OSError:
        pass
    if args.json:
        print(json.dumps(doc, indent=1, default=str))
    else:
        print(f"model self-improvement: {doc['measured']} scored, {doc['unmeasured']} unscored "
              f"-- {doc['status']}")
        for r in doc["predictors"]:
            sk = "  --  " if r["skill"] is None else f"{r['skill']:+.4f}"
            print(f"  {r['status']:11s} skill={sk}  {r['name']}")
            print(f"              predicts {r['predicts']}")
            print(f"              vs baseline: {r['baseline']}  ({r['why']})")
        for p in doc["problems"]:
            print(f"  PROBLEM {p}")
    return 0 if doc["status"] == "OK" else 2


if __name__ == "__main__":
    raise SystemExit(main())
