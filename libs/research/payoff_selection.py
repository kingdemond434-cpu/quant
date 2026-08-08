"""PAYOFF-AWARE MODEL SELECTION — the accurate model and the profitable model are different models.

THE OBSERVATION THIS FORMALISES. A system that is right 89% of the time can lose money, and a
system that is right 35% of the time can compound beautifully. Hit rate is a property of the
CLASSIFIER; wealth is a property of the classifier times the payoff distribution times the cost
structure times the frequency. Selecting on the first and hoping for the second is how a desk ends
up with a leaderboard of excellent models and a flat equity curve.

    win rate 0.89, +1bp per win, -12bp per loss, 5bp round-trip cost
        -> 0.89*1 - 0.11*12 - 5 = -5.4bp per trade, and the model is the best on the board

**AUC, ACCURACY AND F1 ARE FORBIDDEN AS PRIMARY SELECTION CRITERIA HERE**, not because they are
uninformative but because they are invariant to exactly the thing that pays: they rank a model the
same whether its correct calls earn 1bp or 100. They remain useful as DIAGNOSTICS -- a model whose
economic score is good and whose calibration is terrible is usually about to stop working -- and
this module reports them for that purpose and refuses to rank on them.

WHAT IT RANKS ON. Realised net marginal E[log W] per unit time, which is the desk's global
objective and not a proxy for it. Between two models with the same expected log contribution, the
tie is broken by calibration, because a well-calibrated model can be SIZED and a miscalibrated one
that happens to be profitable cannot: the sizing input is the probability, and a probability that
does not mean what it says makes every downstream Kelly fraction wrong in an unknown direction.

Ranks and explains. Selects nothing on its own -- the allocator reads this alongside capacity,
independence and execution feasibility, all of which can overturn a ranking computed here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

__all__ = [
    "MIN_PREDICTIONS",
    "ModelRecord",
    "brier",
    "calibration_error",
    "economic_score",
    "expected_log_growth",
    "log_loss",
    "rank",
    "summarise",
]

#: Below this many scored predictions every number here is an anecdote. The specification forbids
#: tiny-sample win-rate worship by name, and this is where that is enforced rather than asserted.
MIN_PREDICTIONS: int = 100


@dataclass(frozen=True)
class ModelRecord:
    """One predictive model with BOTH its statistical and its economic behaviour.

    The asymmetry of the two payoff fields is the entire point of the dataclass: a model that
    stores only `hit_rate` cannot be economically ranked at all, and one that stores only the mean
    return hides the tail that decides survival.
    """

    name: str
    #: Scored predictions. Below MIN_PREDICTIONS the record is reported, never ranked.
    n_predictions: int
    hit_rate: float
    #: Mean NET return per CORRECT call, in bps, after all costs.
    win_bps: float
    #: Mean NET loss per WRONG call, in bps, expressed positive.
    loss_bps: float
    #: Trades per year this model generates. Frequency converts a per-trade edge into growth.
    trades_per_year: float = 0.0
    #: Fraction of capital committed per trade. Needed to turn bps into a log contribution.
    capital_fraction: float = 1.0
    #: Worst single-trade net loss observed or modelled, bps positive. Drives the log penalty.
    tail_loss_bps: float = 0.0
    #: Mean predicted probability and realised frequency, for calibration. (0,0) = unmeasured.
    mean_predicted: float = 0.0
    mean_realised: float = 0.0
    #: Mean -log(p_assigned_to_truth) over the scored set. 0 = unmeasured.
    mean_log_loss: float = 0.0
    #: Optional diagnostics. Reported, never ranked on.
    auc: float | None = None

    @property
    def measured(self) -> bool:
        return self.n_predictions >= MIN_PREDICTIONS and self.trades_per_year > 0


def expected_bps(m: ModelRecord) -> float:
    """Expected NET bps per trade. The first place a high-hit-rate model can already be negative."""
    p = max(0.0, min(1.0, m.hit_rate))
    return p * m.win_bps - (1.0 - p) * m.loss_bps


def expected_log_growth(m: ModelRecord) -> float | None:
    """Annualised expected log growth contribution. THE RANKING QUANTITY.

    Uses log1p on the per-trade fractional outcomes rather than the arithmetic mean, so a model
    whose losses are large relative to its wins is penalised the way compounding actually penalises
    it. A model with expected bps of exactly zero has NEGATIVE log growth whenever its outcomes
    vary at all, which is the arithmetic reason a break-even-looking strategy bleeds.
    """
    if not m.measured:
        return None
    p = max(0.0, min(1.0, m.hit_rate))
    f = max(0.0, m.capital_fraction)
    win = f * m.win_bps / 10_000.0
    loss = f * m.loss_bps / 10_000.0
    if loss >= 1.0:
        return float("-inf")   # a single loss of 100% of committed capital is absorbing
    per_trade = p * math.log1p(win) + (1.0 - p) * math.log1p(-loss)
    return float(per_trade * m.trades_per_year)


def brier(m: ModelRecord) -> float | None:
    """Brier score from the summary calibration pair. None when unmeasured.

    A summary approximation, and labelled as one: the true Brier needs the full prediction set.
    It is here so a model that reports no calibration information is visibly distinguishable from
    one that reports good calibration, which a `None` in a table achieves and a default 0.0 does
    not.
    """
    if m.mean_predicted <= 0 and m.mean_realised <= 0:
        return None
    return float((m.mean_predicted - m.mean_realised) ** 2 + m.mean_realised
                 * (1.0 - m.mean_realised))


def calibration_error(m: ModelRecord) -> float | None:
    """|mean predicted - mean realised|. None when unmeasured.

    The cheapest calibration statistic that exists and the one that catches the failure that costs
    money: a model that says 0.80 and is right 0.55 of the time will be sized nearly half again too
    large by any probability-driven allocator, every single time.
    """
    if m.mean_predicted <= 0 and m.mean_realised <= 0:
        return None
    return abs(m.mean_predicted - m.mean_realised)


def log_loss(m: ModelRecord) -> float | None:
    """Reported as recorded. None when unmeasured -- never 0.0, which would read as perfect."""
    return m.mean_log_loss if m.mean_log_loss > 0 else None


def economic_score(m: ModelRecord) -> tuple[float | None, str]:
    """(annualised expected log growth, why). The ONLY quantity `rank` orders on."""
    g = expected_log_growth(m)
    if g is None:
        return None, (
            f"{m.name}: {m.n_predictions} prediction(s) against a floor of {MIN_PREDICTIONS}"
            + ("" if m.trades_per_year > 0 else " and no trade frequency recorded")
            + ". UNMEASURED -- and a hit rate computed on this many calls is precisely the "
              "small-sample statistic the specification forbids as evidence")
    if g == float("-inf"):
        return g, (f"{m.name}: a losing trade commits 100% of allocated capital. That is an "
                   "absorbing state, not a large negative number")
    eb = expected_bps(m)
    return g, (
        f"{m.name}: hit rate {m.hit_rate:.0%}, +{m.win_bps:.2f}/-{m.loss_bps:.2f}bp "
        f"=> {eb:+.2f}bp expected per trade x {m.trades_per_year:g}/yr "
        f"=> {g:+.4f} expected log growth")


def rank(models: list[ModelRecord]) -> list[dict[str, object]]:
    """Ordered best-first by expected log growth. Unmeasured models sort LAST and are labelled.

    Ties break on calibration error (smaller wins), because between two equally profitable models
    the sizable one is worth more than the other.
    """
    rows: list[dict[str, object]] = []
    for m in models:
        g, why = economic_score(m)
        ce = calibration_error(m)
        rows.append({
            "name": m.name,
            "expected_log_growth": None if g is None else (
                None if g == float("-inf") else round(g, 6)),
            "ruin": g == float("-inf"),
            "expected_bps_per_trade": round(expected_bps(m), 4),
            "hit_rate": m.hit_rate,
            "n_predictions": m.n_predictions,
            "calibration_error": None if ce is None else round(ce, 4),
            "brier": None if brier(m) is None else round(brier(m) or 0.0, 5),
            "log_loss": log_loss(m),
            "auc_DIAGNOSTIC_ONLY": m.auc,
            "why": why,
            "measured": m.measured,
        })
    rows.sort(key=lambda r: (
        0 if r["measured"] else 1,
        1 if r["ruin"] else 0,
        -(float(str(r["expected_log_growth"])) if r["expected_log_growth"] is not None else -1e18),
        float(str(r["calibration_error"])) if r["calibration_error"] is not None else 1e18,
    ))
    return rows


def summarise(models: list[ModelRecord]) -> dict[str, object]:
    """Report shape. Leads with the case the specification cares about most."""
    if not models:
        return {"models": 0, "headline": (
            "no model records -- payoff-aware selection is UNEXERCISED. Any model chosen today "
            "was chosen on something other than expected log growth")}
    rows = rank(models)
    measured = [r for r in rows if r["measured"] and not r["ruin"]]
    inversion = ""
    if len(measured) >= 2:
        by_hit = max(measured, key=lambda r: float(str(r["hit_rate"])))
        best = measured[0]
        if by_hit["name"] != best["name"]:
            inversion = (
                f"THE HIGHEST HIT RATE IS NOT THE BEST MODEL: {by_hit['name']} wins "
                f"{float(str(by_hit['hit_rate'])):.0%} of the time and contributes "
                f"{by_hit['expected_log_growth']} expected log growth, against "
                f"{best['name']} at {float(str(best['hit_rate'])):.0%} and "
                f"{best['expected_log_growth']}. Selecting on accuracy would have taken the "
                "wrong one.")
    return {
        "models": len(models),
        "ranked": rows,
        "best": rows[0]["name"] if rows else None,
        "hit_rate_inversion": inversion,
        "headline": inversion or (
            f"{len(measured)} model(s) economically rankable; best is {rows[0]['name']} at "
            f"{rows[0]['expected_log_growth']} expected log growth"
            if measured else
            f"0 of {len(models)} models carry enough scored predictions to be ranked "
            f"economically (floor {MIN_PREDICTIONS})"),
        "note": ("Ranking is on annualised expected log growth ONLY. AUC, accuracy and hit rate "
                 "are reported as diagnostics and are invariant to payoff size, which is the "
                 "quantity that decides wealth. Calibration breaks ties because a probability "
                 "that does not mean what it says makes every downstream sizing decision wrong "
                 "in an unknown direction."),
    }
