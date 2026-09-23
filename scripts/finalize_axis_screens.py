"""Post-process the 2026-07-26 axis screens: correct a harness annualization defect, attach
IC t-statistics, apply the multiplicity bar, and write the axis-level verdicts.

WHY THIS EXISTS -- HARNESS DEFECT FOUND DURING THIS CAMPAIGN
-----------------------------------------------------------
`libs/research/axis_screen.py::_sh` computes

    rr = np.sign(sig) * fv;  return rr.mean() / rr.std() * np.sqrt(365)

The sqrt(365) is HARDCODED, i.e. it assumes every element of `target_ret` is a ONE-DAY return.
But the documented way to test the 5d/20d horizons the mandate requires is to hand the harness
NON-OVERLAPPING DOWNSAMPLED periods (this is exactly what the desk's own
scripts/screen_cme_basis.py does). When each element is a k-day return there are 365/k periods
per year, so the correct factor is sqrt(365/k) -- and the reported Sharpe is inflated by sqrt(k):
~2.24x at 5d and ~4.47x at 20d. Verified by simulation against an analytically-known Sharpe
(inflation measured 1.51x at 5d and 3.99x at 20d, converging on sqrt(k) as noise shrinks).

TWO CONSEQUENCES, BOTH BAD, BOTH AFFECTING WORK ALREADY ON FILE:
  1. The sharpe_min=0.5 promotion floor is effectively 0.22 at 5d and 0.11 at 20d, so downsampled
     screens are systematically OVER-promoted to SCREEN-INTERESTING.
  2. The sharpe_ceiling=6.0 SUSPECT-LOOKAHEAD rail -- the safety rail that caught the bithumb
     IC-0.72/Sharpe-10 fake -- is effectively 13.4 at 5d and 26.8 at 20d. THE LOOKAHEAD RAIL IS
     PARTLY BLIND AT LONG HORIZONS. That is the more dangerous of the two.
  3. Already on file: reports/axis_screens/cme_basis_20260724.json trial `cme_basis_ann->btc_5d`
     is recorded SCREEN-INTERESTING at Sharpe 1.74; corrected it is 0.78.

The audited harness is NOT edited here -- changing it is a desk decision requiring its own review.
The correction is applied transparently at the reporting layer and flagged for the CRO.

MULTIPLICITY: the desk's own history (420 price-family hypotheses, 0 survivors) is the reason a
nominal pass means nothing without a multiplicity bar. Each trial's IC t-stat is compared against
a Bonferroni bar at alpha=0.05 both per-axis and campaign-wide across all 37 screened trials.
"""

from __future__ import annotations

import json
import math
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
OUT = _ROOT / "reports" / "axis_screens"
SHARPE_MIN, IC_MIN = 0.5, 0.03

#: Horizon for a Stage-A forecast. 30d matches research_cycle's engineering horizon: long enough
#: for a survivor to actually reach a forward slot, short enough that the check_calibration OVERDUE
#: fence still bites inside a quarter.
_FORECAST_HORIZON_DAYS = 30
#: Pre-registered probability that a Stage-A survivor reaches Stage-B. LOW ON PURPOSE, and the
#: number is the desk's own history: 420 price-family hypotheses, zero survivors. L1.6 says a
#: screen hit is not an edge and screens carry zero promotion authority -- this forecast is the
#: measurement of exactly how little a screen hit is worth, so that the claim stops being folklore.
_P_SCREEN_REACHES_STAGE_B = 0.15


def _log_screen_forecasts(axis: str, survivors: list[dict[str, Any]]) -> None:
    """PRE-REGISTER what a SCREEN-INTERESTING verdict is implicitly predicting (R0112, L1.29a).

    Stage A publishes verdicts and spends the desk's attention on them, but no screen has ever been
    logged as a forecast -- so "screens have zero promotion authority" stayed an assertion nobody
    could score. Every survivor here is an implicit claim that this hit is one of the few that
    goes somewhere; this writes that claim down BEFORE the answer is known, with a resolve_by.

    NEVER RESOLVED HERE. A forecast graded in the pass that logged it is the degenerate all-TRUE
    row forecast_calibration._scoreable exists to exclude (30 such rows once inverted the desk's
    measured bias into kelly_leverage). This function only ever pre-registers, and the outcome is
    genuinely unknown today -- the 30 days have not passed.

    One row per (axis, trial), resolve_by FIXED at first assertion: get_forecast() short-circuits
    re-runs, so re-finalizing an axis cannot roll the deadline forward (a rolling deadline never
    goes overdue, which would blind the check_calibration fence) or mint duplicate rows for what
    is arithmetically one observation.
    """
    if not survivors:
        return
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    try:
        from libs.self_improvement import forecast_calibration as fc
    except ImportError:
        return
    now = datetime.now(tz=UTC)
    resolve_by = (now + timedelta(days=_FORECAST_HORIZON_DAYS)).isoformat()
    for t in survivors:
        key = f"screen:{axis}:{t['name']}"
        if fc.get_forecast(key) is not None:
            continue                                    # pre-registered already
        fc.log_forecast(
            key, _P_SCREEN_REACHES_STAGE_B, "screen_promotion", resolve_by=resolve_by,
            claim=(f"Stage-A survivor {axis}/{t['name']} (corrected Sharpe "
                   f"{t.get('sharpe_best_corrected')}, IC t={t.get('ic_t_stat')}) reaches a "
                   f"Stage-B forward slot within {_FORECAST_HORIZON_DAYS}d of "
                   f"{now.date().isoformat()}"))


def _step(name: str) -> int:
    m = re.search(r"_(\d+)d\b", name.replace("->", "_"))
    if not m:
        return 1
    v = int(m.group(1))
    return v if v in (1, 5, 20) else 1


def _norm_ppf(p: float) -> float:
    """Acklam inverse-normal, good to ~1e-9 -- avoids a scipy dependency."""
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    pl = 0.02425
    if p < pl:
        q = math.sqrt(-2 * math.log(p))
        return ((((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5])
                / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1))
    if p > 1 - pl:
        q = math.sqrt(-2 * math.log(1 - p))
        return (-(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5])
                / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1))
    q, r = p - 0.5, (p - 0.5) ** 2
    return ((((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q
            / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1))


def _bar(m: int) -> float:
    """Two-sided Sidak/Bonferroni t-bar for m trials. An EMPTY family has no bar (L1.57).

    Crashed with ZeroDivisionError on m=0 until 2026-08-29, and it reached m=0 for real: an axis
    whose report holds trials but none with both a `verdict` and a non-zero `n` screens to an
    empty list, and the exception killed the whole organ mid-loop, so every axis ORDERED AFTER
    the empty one was silently never finalized. Live repro: etf_flows and
    liquidation_reversion_BTCUSDT printed, then the process died at line 310.

    The bar returned here must be one NOTHING can clear. Returning 0 -- the other obvious way to
    make the arithmetic not raise -- would admit every trial in a family the desk never measured,
    and "a verdict over an empty population is vacuous, never a pass" is the law this would break
    in the one direction no downstream gate re-checks.
    """
    if m < 1:
        return math.inf
    return round(abs(_norm_ppf(0.05 / (2 * m))), 2)


#: The axes this correction layer was WRITTEN for. It is a historical record, not the work list:
#: every screen the desk has shipped since is absent from it, and on 2026-08-05 all three names
#: here referred to files that do not exist while the three screens that DO exist
#: (announcement_diffusion, liquidation_reversion_BTCUSDT, unlock_supply_series) were invisible
#: to this organ entirely. A hardcoded roster processes the desk that existed when it was typed.
AXES = ("mining", "wikipedia", "fx")


def _axes_on_disk() -> tuple[str, ...]:
    """Every screen actually present, unioned with the historical AXES list.

    THE WORK LIST IS WHAT IS ON DISK. Iterating a hardcoded tuple meant a screen shipped after
    this file was written could never be corrected, could never receive `verdict_adjusted`, and
    could therefore never be admitted to a forward slot -- so a new axis silently could not
    produce a survivor no matter what it measured. The union keeps the historical names so their
    ABSENCE is still reported rather than quietly forgotten.
    """
    found = sorted(p.stem for p in OUT.glob("*.json")) if OUT.exists() else []
    return tuple(dict.fromkeys([*AXES, *found]))
def _trial_line(t: dict[str, Any]) -> str:
    """One summary line per trial, total function: trials arrive in more than one screen shape
    (an event-study row carries no `ic`), and the 2026-08-12 crash proved a KeyError HERE aborts
    every axis after the one being printed -- their reports never finalize, so their screens can
    admit nothing to a forward slot. A missing metric prints as `?`, never kills the finalizer.
    """
    ic, tt = t.get("ic"), t.get("ic_t_stat")
    sr, sc = t.get("sharpe_best_reported"), t.get("sharpe_best_corrected")
    num = (int, float)
    ic_s = f"{ic:+.4f}" if isinstance(ic, num) else "?"
    tt_s = f"{tt:.2f}" if isinstance(tt, num) else "?"
    sh_s = (f"{sr:.2f}->{sc:.2f}"
            if isinstance(sr, num) and isinstance(sc, num) else "?")
    return (f"  {t.get('name', '?'):46s} IC={ic_s} t={tt_s} Sh {sh_s}  "
            f"{str(t.get('verdict_adjusted', ''))[:58]}")


TOTAL_TRIALS = 37  # 12 mining + 13 wikipedia + 12 fx (+ etf_flows not screenable)
CAMPAIGN_BAR = _bar(TOTAL_TRIALS)

VERDICTS = {
    "mining": (
        "NO SURVIVOR. 12 pre-declared trials, 3 printed a nominal SCREEN-INTERESTING and none "
        "survives correction. (a) The single best, hash_ribbon->btc_5d (IC +0.093), has the "
        "OPPOSITE SIGN to the pre-registered mechanism: capitulation was predicted to be FOLLOWED "
        "by higher returns (negative IC), and a positive IC says rising hashrate leads rising "
        "price. Per the graveyard's xsec_lowvol rule the sign is NOT flipped and re-sold as "
        "momentum. (b) Its sign also INVERTS between adjacent horizons (+0.093 at 5d, -0.113 at "
        "20d) -- the signature of noise, not structure. (c) Corrected Sharpe 0.83, and its IC "
        "t=2.02 fails both the per-axis (2.87) and campaign (3.20) bars. (d) difficulty_5d and "
        "hashprice_usd_5d fall below the 0.5 Sharpe floor once the annualization is corrected. "
        "ONE GENUINE POSITIVE FINDING: the ribbon is NOT lagged price momentum -- the raw ribbon "
        "level correlates +0.30 with trailing 60d BTC return, but the 20d Z-SCORE the harness "
        "actually screens correlates only +0.01..+0.04, so the z-scoring strips the momentum "
        "component. The construction is genuinely orthogonal to the trend book; it simply has no "
        "edge. The pre-registered contamination prediction for hashprice_usd was also CONFIRMED "
        "(same-period corr 0.157 vs 0.007 for the BTC-denominated twin), reproducing the cm_mvrv "
        "price-numerator lesson on a new dataset."),
    "wikipedia": (
        "NO SURVIVOR -- and the result CLOSES THE TWO ESCAPE HATCHES the graveyarded "
        "multilingual_wikipedia_attention kill left open. That kill kept the door ajar for a "
        "different OBJECT and a different TARGET; both are now tested and both fail. (a) Gateway/"
        "onboarding attention (Coinbase+Binance+Cryptocurrency = purchase intent, which should "
        "LEAD deposits, unlike news-reading which LAGS the print) is weak at every horizon: the "
        "5d nominal pass corrects to Sharpe 0.39, below the floor. (b) Cross-sectional relative "
        "attention as an ASSET-SELECTION signal fails on sign stability: ETH flips -0.042 (1d) -> "
        "+0.052 (5d) -> +0.011 (lagged); SOL is -0.001 (1d) but +0.055 LAGGED, i.e. STRONGER with "
        "a stale signal, which is mechanically incoherent for an attention signal that should "
        "decay in hours and is a clean noise tell. DOGE 1d carries same-period corr 0.18, close to "
        "the 0.20 contamination bar -- meme attention co-moves with meme price, exactly the "
        "'attention co-moves with, does not lead' finding of the original kill. Nothing clears the "
        "per-axis (2.87) or campaign (3.20) multiplicity bar. Extends the existing kill from "
        "'not a daily timing signal' to 'not an asset-selection signal either'."),
    "fx": (
        "NO SURVIVOR, and the axis AS INGESTED CANNOT TEST ITS OWN MECHANISM. The fx lake holds 57 "
        "crosses and not one high-barrier currency (no KRW, CNY/CNH, BRL, ARS, NGN, VND, EGP, "
        "INR); EURRUB terminates 2022-02-28 on the sanctions cut. The graveyard's era-evidence "
        "entry states the governing law -- premium magnitude tracks BARRIER HEIGHT -- so the only "
        "currencies available are precisely the ones the mechanism predicts should NOT pay. That "
        "is a data-coverage verdict, not an economic one. Of 12 trials: the EM debasement basket "
        "is weak at 1d/20d and its 5d nominal pass corrects to Sharpe 0.32; synthetic DXY is weak "
        "everywhere; TRY-only is weak, independently reproducing the graveyard's finding that "
        "Turkey arbs global too tightly. TWO DIAGNOSTICS EARNED THEIR KEEP. (1) DENOMINATION "
        "CONTROL: the same signal scores HIGHER against BTC priced in TRY (IC +0.043) than against "
        "BTC/USDT (+0.032) -- because BTC-in-TRY return mechanically CONTAINS the next TRY move, "
        "so that build is partly FX autocorrelation, not a crypto edge. This is why both "
        "denominations must be logged. (2) SHIFT TEST: at +1d -- deliberately feeding the signal "
        "from the FUTURE -- |IC| jumps 5x to 0.073, while at -1d it is flat at 0.015. A "
        "relationship that is far stronger when you peek forward is CONTEMPORANEOUS, not leading: "
        "EM FX and BTC both load on the same global risk factor and the 20d depreciation is a "
        "LAGGING read of risk-off that already happened. There is no lead to trade."),
}
NEXT = {
    "mining": ("Do NOT clock and do NOT fish further hashrate variants -- 12 trials is already the "
               "multiplicity budget for this axis. The mechanism is not refuted, only the daily/"
               "weekly public aggregates are: hashrate and difficulty are network-wide averages "
               "that cannot see WHICH cohort is capitulating. "
               "The honest escalation, pre-registered "
               "and on its own clock slot, is miner TREASURY OUTFLOWS (known miner wallet -> "
               "exchange transfers), which observes the forced selling directly rather than "
               "inferring it from a Poisson-noisy block-count estimate."),
    "wikipedia": ("Do NOT clock. Recommend the graveyard entry for "
                  "multilingual_wikipedia_attention "
                  "be AMENDED to record that the object arm (gateway/onboarding pages) and the "
                  "target arm (cross-sectional asset selection) have now also been tested and "
                  "failed, so the category is closed on all three arms and no future agent spends "
                  "budget re-opening it."),
    "fx": ("Do NOT clock. The productive action is INGESTION, not more screening: this axis "
           "deserves its high prior only if the lake carries high-barrier currencies. Request "
           "USDKRW, USDCNY/CNH, USDBRL, USDARS, USDNGN, USDVND before any further fx screening. "
           "Re-screening the majors would be breadth-mining the currencies the mechanism already "
           "predicts pay nothing. "
           "RUB is re-testable as a data/infra kill if the feed is restored."),
}


def main() -> None:
    # CONVERT FIRST. Every screen that writes its own schema is translated into the canonical
    # `trials` shape before the correction layer looks at the directory, so a newer screen stops
    # being INCOMPATIBLE-forever and starts being corrected like anything else. Measured
    # 2026-08-05: 120 scored cells across four artifacts were sitting unreadable here while the
    # desk reported "no survivors" -- output produced, never converted, never utilised.
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    from libs.research.screen_conversion import write_converted
    conv = write_converted(_ROOT)
    if conv["written"]:
        print(f"converted {conv['n_cells']} scored cell(s) from {conv['n_artifacts']} artifact(s) "
              f"into the canonical shape: {', '.join(conv['written'])}")
    if conv["removed_stale"]:
        print(f"  removed stale conversions (source gone): {', '.join(conv['removed_stale'])}")
    for s in conv["skipped"]:
        print(f"  NOT CONVERTED {s['path']}#{s['key']}: {s['why']}")

    summary = []
    missing: list[str] = []
    incompatible: list[str] = []
    vacuous: list[str] = []
    unreadable: list[str] = []
    for axis in _axes_on_disk():
        p = OUT / f"{axis}.json"
        # A MISSING SCREEN IS A SKIP, NOT A CRASH -- and this line was the single point of
        # failure between the desk and its first forward clock.
        #
        # AXES is a hardcoded list of screens the desk expects to exist. When one of them has not
        # been run (mining.json, on 2026-08-05), the unguarded read_text raised FileNotFoundError
        # and this organ died before writing `verdict_adjusted` to ANY report -- including the
        # three that were present and finished. run_paper_sleeve_spawner then refused with
        # "NONE carries verdict_adjusted", so no Stage-A candidate could ever be admitted to a
        # forward slot, so no clock ever started, so NOTHING COULD EVER SURVIVE. Ten of twelve
        # Stage-B slots idle, 0 clocks accruing, none ever started -- all of it downstream of one
        # unguarded read on a file nobody had produced.
        #
        # The missing screens are NAMED in the artifact rather than silently skipped: "this axis
        # has not been screened" and "this axis was screened and corrected" are different facts,
        # and collapsing them is how a gap in coverage reads as a completed sweep.
        if not p.exists():
            missing.append(axis)
            continue
        try:
            rep = json.loads(p.read_text("utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            unreadable.append(f"{axis} ({type(exc).__name__})")
            continue
        # A THIRD STATE, and it must not collapse into either of the other two. This correction
        # layer speaks ONE artifact schema -- a `trials` list from the axis-screen harness. The
        # newer Stage-A screens (announcement_diffusion, unlock_supply_series, venue_subsidy...)
        # write a different shape. Those are neither MISSING (they ran, and produced results) nor
        # CORRECTED (this layer cannot read them), and calling them either one is a lie in a
        # different direction: "missing" hides completed work, "corrected" claims a multiplicity
        # charge that was never applied. Named as INCOMPATIBLE so the gap is a work item with an
        # owner rather than a silence.
        if not isinstance(rep.get("trials"), list):
            incompatible.append(axis)
            continue
        screened = [t for t in rep["trials"] if "verdict" in t and t.get("n")]
        axis_bar = _bar(len(screened))
        if not screened:
            # VACUOUS, not corrected and not missing: the axis produced a report, and nothing in
            # it is judgeable. Recorded by name so an empty family is a work item rather than a
            # zero that reads like a clean sweep.
            vacuous.append(axis)
            continue
        for t in screened:
            k = _step(t["name"])
            best = max(abs(t.get("sharpe_momentum", 0)), abs(t.get("sharpe_reversal", 0)))
            corr = round(best / math.sqrt(k), 2)
            t["period_days"] = k
            t["sharpe_best_reported"] = best
            t["sharpe_best_corrected"] = corr
            t["sharpe_correction_note"] = (
                "harness hardcodes sqrt(365); for k-day periods the correct factor is "
                f"sqrt(365/{k}), so reported Sharpe is inflated by "
                f"sqrt({k})={round(math.sqrt(k),2)}x"
                if k > 1 else "1d periods -- harness annualization correct, no adjustment")
            tstat = round(abs(t.get("ic", 0)) * math.sqrt(max(t["n"] - 2, 1)), 2)
            t["ic_t_stat"] = tstat
            t["clears_axis_multiplicity_bar"] = bool(tstat > axis_bar)
            t["clears_campaign_multiplicity_bar"] = bool(tstat > CAMPAIGN_BAR)
            # Controls and future-peeking diagnostics can NEVER be candidates, however they score.
            # SHIFT_*_plus1d feeds the signal from the FUTURE; a strong score there is evidence of
            # contemporaneous co-movement (an ARTIFACT), which rule 8 says is never an edge.
            nm = t["name"]
            up = nm.upper().replace("_", "-")
            # CASE- AND SEPARATOR-INSENSITIVE, and it must be. The original test matched the exact
            # uppercase-hyphen spellings this layer's first three screens happened to use. The
            # converted screens spell the same thing `lookahead_control`, so the match missed,
            # execution fell to the `else` branch below, and that branch set is_candidate=True --
            # which SPAWNED TWO DECLARED LOOK-AHEAD CONTROLS AS FORWARD CLOCKS on 2026-08-05
            # (etf_creation_pressure|lookahead_control, stablecoin_net_mint_usdc|lookahead_control).
            # A control exists to MEASURE a leak; promoting one is the rule-8 artifact-as-edge
            # failure, and it would have spent two of twelve Holm slots confirming that the future
            # predicts the present.
            is_ctrl = any(k in up for k in ("DENOM-CONTROL", "LOOKAHEAD-CONTROL", "SHIFT-",
                                            "-LAG1D", "-CONTROL"))
            # A CONVERTER'S EXPLICIT DISQUALIFICATION IS NEVER UPGRADED HERE. Upstream knows things
            # this name-matcher cannot see -- `alignment.is_lookahead_control`, a diagnostic build
            # form -- so `is_candidate: False` arriving on the row is a decision, not a default,
            # and no branch below may overwrite it with True.
            pre_disqualified = t.get("is_candidate") is False
            if is_ctrl or pre_disqualified:
                kind = (str(t.get("conversion_disqualified")) if pre_disqualified and not is_ctrl
                        else "future-peeking shift diagnostic" if "plus1d" in nm.lower() else
                        "denomination artifact control" if "DENOM-CONTROL" in up else
                        "look-ahead control" if "LOOKAHEAD-CONTROL" in up else
                        "conservative-lag robustness check")
                t["is_candidate"] = False
                t["verdict_adjusted"] = (
                    f"NOT-A-CANDIDATE ({kind}; raw harness verdict {t['verdict']}). "
                    "Diagnostics are read for what they reveal, never promoted.")
            elif t["verdict"] == "SCREEN-INTERESTING":
                t["is_candidate"] = True
                if corr < SHARPE_MIN:
                    t["verdict_adjusted"] = ("SCREEN-WEAK (Sharpe fails the 0.5 floor once the "
                                             "harness annualization defect is corrected)")
                elif not t["clears_campaign_multiplicity_bar"]:
                    t["verdict_adjusted"] = (f"SCREEN-WEAK (IC t={tstat} fails the multiplicity "
                                             f"bar: axis {axis_bar}, campaign {CAMPAIGN_BAR})")
                else:
                    t["verdict_adjusted"] = "SCREEN-INTERESTING (survives correction+multiplicity)"
            else:
                t["is_candidate"] = True
                t["verdict_adjusted"] = t["verdict"]
        rep["harness_defect_found"] = {
            "location": "libs/research/axis_screen.py::_sh (line ~69)",
            "defect": "np.sqrt(365) hardcoded; assumes 1-day target periods",
            "impact": ("downsampled 5d/20d screens report Sharpe inflated by sqrt(k) (2.24x / "
                       "4.47x). Promotion floor effectively 0.22/0.11 and -- more dangerous -- the "
                       "SUSPECT-LOOKAHEAD ceiling of 6.0 becomes 13.4/26.8, so the rail that "
                       "caught bithumb is partly blind at long horizons."),
            "also_affects": "reports/axis_screens/cme_basis_20260724.json (5d Sharpe 1.74 -> 0.78)",
            "action": "NOT patched here -- harness is audited; flagged for CRO decision.",
        }
        rep["multiplicity"] = {"axis_trials": len(screened), "axis_bonferroni_t": axis_bar,
                               "campaign_trials": TOTAL_TRIALS,
                               "campaign_bonferroni_t": CAMPAIGN_BAR}
        # VERDICTS is hand-written prose per axis and only covers the three this layer was
        # authored for. A screen without one is still CORRECTED -- the arithmetic above ran and
        # verdict_adjusted is on every trial; what is absent is the human summary. Saying so is
        # the honest gap, and it is a smaller one than crashing after doing all the work.
        rep["verdict"] = VERDICTS.get(
            axis, f"NO HAND-WRITTEN VERDICT for {axis}: the correction arithmetic ran and every "
                  "trial carries verdict_adjusted, but nobody has written the prose summary that "
                  "names what this axis measured and what it means. Mechanical result stands; "
                  "the interpretation is owed.")
        rep["forward_clock"] = (
            "NO -- no construction survived; Stage A has zero promotion authority")
        rep["next_step"] = NEXT.get(
            axis, "NO NEXT STEP RECORDED for this axis -- write one. A corrected screen with no "
                  "stated next move is where the pipeline stalls silently: the arithmetic is "
                  "done, nobody is told what to do with it, and it sits.")
        p.write_text(json.dumps(rep, indent=1, default=str), "utf-8")

        surv = [t for t in screened if t["verdict_adjusted"].startswith("SCREEN-INTERESTING")]
        _log_screen_forecasts(axis, surv)
        summary.append((axis, len(screened), len(surv)))
        print(f"\n=== {axis}: {len(screened)} trials, {len(surv)} survive correction+multiplicity "
              f"(axis bar t>{axis_bar}, campaign t>{CAMPAIGN_BAR}) ===")
        for t in sorted(screened, key=lambda x: -abs(x.get("ic", 0)))[:5]:
            print(_trial_line(t))
    if vacuous:
        print(f"\n  VACUOUS -- report present, ZERO judgeable trials ({len(vacuous)}): "
              f"{', '.join(vacuous)}. No multiplicity bar exists over an empty family (L1.57); "
              "this is an unmeasured axis, never a clean one.")
    if incompatible:
        print(f"\n  PRESENT BUT NOT CORRECTABLE BY THIS LAYER ({len(incompatible)}): "
              f"{', '.join(incompatible)}")
        print("  -- these screens RAN and produced results in a schema this correction layer "
              "does not speak (no `trials` list). They are not missing and they are not "
              "corrected. Until a reader exists for their shape they carry no verdict_adjusted, "
              "so run_paper_sleeve_spawner cannot admit them to a forward slot -- which is the "
              "difference between a screen that found nothing and a screen nobody can promote.")
    if unreadable:
        print(f"\n  UNREADABLE ({len(unreadable)}): {', '.join(unreadable)}")
    if missing:
        print(f"\n  NOT SCREENED ({len(missing)}): {', '.join(missing)}")
        print("  -- named rather than skipped: an unscreened axis and a corrected one are "
              "different facts, and collapsing them makes a coverage gap read as a finished "
              "sweep. These produce no verdict_adjusted and can admit nothing to a forward slot.")
    print("\n", summary)


if __name__ == "__main__":
    main()
