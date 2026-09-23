"""s22 -- run s21's homogeneity falsifier score(k*s)==score(s) against the DESK's own scorers.

s21 derived the falsifier from a BRAIN generator whose optimum was zero exposure and applied it to
exactly one desk function. This applies it to the money-path-relevant population. Writes JSON, no
production import side effects, no state mutation.
"""
from __future__ import annotations
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import numpy as np

out: dict = {"probe": "brain_hunter_s22_homogeneity_screen", "date": "2026-08-29", "arms": {}}
KS = [1e-3, 1e-2, 0.1, 1.0, 10.0, 100.0]

def verdict(vals):
    v = np.array(vals, dtype=float)
    if np.allclose(v, v[0], rtol=1e-9, atol=1e-12):
        return "SCALE-INVARIANT"
    if np.all(np.diff(v) < 0):
        return "MONOTONE-DECREASING (optimum at zero exposure)"
    if np.all(np.diff(v) > 0):
        return "MONOTONE-INCREASING (optimum at infinite exposure)"
    return "SCALE-DEPENDENT (non-monotone)"

# ---- positive control: the s21 BRAIN objective, ported verbatim, must FAIL ----
rng = np.random.default_rng(7)
s0 = np.cumsum(rng.standard_normal(1000)) + 100.0
ret = np.diff(s0, prepend=s0[0]) / s0
def brain_fitness(s, r):
    pc = np.diff(s) / s[:-1]
    sharpe = np.sqrt(252) * pc.mean() / pc.std()
    ic = np.corrcoef(s, r)[0, 1]
    turnover = np.abs(np.diff(s)).mean()
    return 0.4 * sharpe + 0.4 * ic - 0.2 * turnover
ctl = [brain_fitness(k * s0, ret) for k in KS]
out["arms"]["control_brain_zhutoutoutousan"] = {"k": KS, "score": ctl, "verdict": verdict(ctl),
    "expected": "MONOTONE-DECREASING", "role": "positive control -- the probe must reproduce s21"}

# ---- desk scorers ----
from libs.alpha_factory.wq_operators import fitness as wq_fitness
from libs.validation.screen_admission import rank_score, GROSS_TURNOVER_PENALTY
from libs.portfolio.capital_competition import AlphaCandidate, score as cc_score
from libs.signal_engine.alpha_competition_engine import _score as ace_score
from libs.signal_engine.models import AlphaSignal, Direction
from libs.self_improvement.weight_optimizer import WeightCandidate, _score as wo_score
from libs.stage14.score import institutional_portfolio_score

# wq_operators.fitness: inputs are sharpe(deg0), annual_return(deg1), turnover(deg1) -> ratio
v = [wq_fitness(sharpe=1.2, annual_return=0.30 * k, turnover=2.0 * k) for k in KS]
out["arms"]["libs.alpha_factory.wq_operators.fitness"] = {"k": KS, "score": v, "verdict": verdict(v),
    "adjudicated": "MOSTLY CLEAN, WITH A NAMED FLOOR CORNER. annual_return and turnover both scale "
    "with position so their ratio is degree 0 -- invariant for k >= 1 here. BELOW the floor "
    "(floor=0.125, hit at k <= 0.1 in this arm) max(turnover, floor) stops tracking the position "
    "and the score becomes MONOTONE INCREASING in exposure: the floor that bounds the "
    "trade-nothing corner opens the opposite one, rewarding size until turnover clears 0.125. "
    "Harmless today -- the function has zero callers outside tests (III.16) -- but it is the "
    "mirror image of the control's defect and must be known before anything wires it.",
    "floor": 0.125}

# screen_admission.rank_score -- the slot-ordering objective. turnover units are UNDECLARED.
v = [rank_score({}, oos_sharpe=1.2, dsr=0.5, reality_p=0.01, turnover=0.05 * k,
                cost_basis="gross") for k in KS]
out["arms"]["libs.validation.screen_admission.rank_score"] = {"k": KS, "score": v,
    "verdict": verdict(v), "penalty_constant": GROSS_TURNOVER_PENALTY,
    "note": "oos_sharpe is degree 0; the turnover penalty is degree 1 in whatever unit the caller "
            "chose. Mixed degrees -> the same defect class as the control."}
# unit sensitivity at FIXED economics: same candidate, three plausible turnover conventions
sens = {conv: rank_score({}, oos_sharpe=1.2, dsr=0.5, reality_p=0.01, turnover=t,
                         cost_basis="gross")
        for conv, t in {"fraction_of_book_per_day_0.05": 0.05,
                        "trades_per_day_5": 5.0,
                        "annualised_turnover_252x_12.6": 12.6,
                        "notional_traded_usd_50000": 50_000.0}.items()}
sens["no_turnover_field_at_all_None"] = rank_score({}, oos_sharpe=1.2, dsr=0.5, reality_p=0.01,
                                                   turnover=None, cost_basis="gross")
out["arms"]["libs.validation.screen_admission.rank_score"]["unit_convention_sensitivity"] = sens

# capital_competition.score -- edge_bps/vol_bps, both degree 1
v = []
for k in KS:
    c = AlphaCandidate(name="x", edge_bps=8.0 * k, vol_bps=40.0 * k, correlation_to_book=0.2,
                       execution_quality=0.9, effective_n=300)
    v.append(cc_score(c)[0])
out["arms"]["libs.portfolio.capital_competition.score"] = {"k": KS, "score": v, "verdict": verdict(v)}

# alpha_competition_engine._score -- strength is a BOUNDED conviction, not an exposure
v = []
for k in KS:
    st = min(1.0, 0.5 * k)
    v.append(ace_score(AlphaSignal(alpha_id="a", symbol="EURUSD", direction=Direction.BUY,
                                   strength=st, sharpe=1.1, health_score=80.0,
                                   decay_multiplier=0.9)))
out["arms"]["libs.signal_engine.alpha_competition_engine._score"] = {"k": KS, "score": v,
    "verdict": verdict(v),
    "adjudicated": "CLEAN -- the raw verdict is a probe artifact, not a defect. strength is "
    "Field(ge=0,le=1) conviction, so scaling it is scaling a bounded degree-0 input and the curve "
    "shown is the clamp saturating. No exposure enters this score and it cannot be gamed by sizing."}

# weight_optimizer._score -- all bounded ratios
v = []
for k in KS:
    v.append(wo_score(WeightCandidate(alpha_id="a", health_score=min(100.0, 50.0 * k),
                                      decay_multiplier=0.9, regime_match=0.8,
                                      correlation_penalty=0.2)))
out["arms"]["libs.self_improvement.weight_optimizer._score"] = {"k": KS, "score": v,
    "verdict": verdict(v),
    "adjudicated": "CLEAN -- same probe artifact as alpha_competition_engine: all four factors are "
    "bounded 0..1, the curve is health_score saturating at its cap, and no exposure enters."}

# institutional_portfolio_score -- clipped ratios only
v = [institutional_portfolio_score(survival_score=80, geometric_growth_score=60,
        expected_sharpe=1.2, expected_calmar=1.0, capacity_score=70,
        diversification_score=60, tail_risk=0.2, drawdown_risk=0.2, fragility=0.1).score
     for _ in KS]
out["arms"]["libs.stage14.score.institutional_portfolio_score"] = {"k": KS, "score": v,
    "verdict": verdict(v), "note": "every input is _clip01'd -- degree 0 by construction"}

# ---- DECISIVE ARM: does the undeclared unit change the ORDER, not just the level? ----
# Two candidates. A is the better forecaster; B trades less. Same economics, four conventions.
A = dict(oos_sharpe=1.40, dsr=0.60, reality_p=0.01)   # stronger OOS, busier
B = dict(oos_sharpe=1.10, dsr=0.55, reality_p=0.02)   # weaker OOS, calmer
TA, TB = 0.08, 0.02        # fraction-of-book-per-day
order = {}
for conv, mult in {"fraction_per_day (0.08 vs 0.02)": 1.0,
                   "trades_per_day (20 vs 5)": 250.0,
                   "annualised (20.2 vs 5.0)": 252.0,
                   "notional_usd (80k vs 20k)": 1_000_000.0,
                   "field absent (None)": None}.items():
    if mult is None:
        sa = rank_score({}, turnover=None, cost_basis="gross", **A)
        sb = rank_score({}, turnover=None, cost_basis="gross", **B)
    else:
        sa = rank_score({}, turnover=TA * mult, cost_basis="gross", **A)
        sb = rank_score({}, turnover=TB * mult, cost_basis="gross", **B)
    order[conv] = {"A": sa, "B": sb, "winner": "A" if sa > sb else "B", "gap": sa - sb}
out["arms"]["ORDERING_INVERSION__screen_admission.admit"] = {
    "question": "admit() sorts forward-slot candidates by rank_score. Does the caller's choice of "
                "turnover unit -- which no signature, docstring or schema declares -- change WHO "
                "gets the scarce forward clock?",
    "candidates": {"A": A, "B": B, "turnover_fraction_per_day": {"A": TA, "B": TB}},
    "by_convention": order,
    "distinct_winners": sorted({v["winner"] for v in order.values()}),
}

print(json.dumps(out, indent=2, default=float))
Path(ROOT / "data" / "brain_hunter_s22_homogeneity_screen.json").write_text(
    json.dumps(out, indent=2, default=float), encoding="utf-8")
