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
from datetime import UTC, datetime
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "reports" / "axis_screens"
SHARPE_MIN, IC_MIN = 0.5, 0.03


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
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > 1 - pl:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q, r = p - 0.5, (p - 0.5) ** 2
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


def _bar(m: int) -> float:
    return round(abs(_norm_ppf(0.05 / (2 * m))), 2)


AXES = ("mining", "wikipedia", "fx")
TOTAL_TRIALS = 37                      # 12 mining + 13 wikipedia + 12 fx (+ etf_flows not screenable)
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
               "that cannot see WHICH cohort is capitulating. The honest escalation, pre-registered "
               "and on its own clock slot, is miner TREASURY OUTFLOWS (known miner wallet -> "
               "exchange transfers), which observes the forced selling directly rather than "
               "inferring it from a Poisson-noisy block-count estimate."),
    "wikipedia": ("Do NOT clock. Recommend the graveyard entry for multilingual_wikipedia_attention "
                  "be AMENDED to record that the object arm (gateway/onboarding pages) and the "
                  "target arm (cross-sectional asset selection) have now also been tested and "
                  "failed, so the category is closed on all three arms and no future agent spends "
                  "budget re-opening it."),
    "fx": ("Do NOT clock. The productive action is INGESTION, not more screening: this axis "
           "deserves its high prior only if the lake carries high-barrier currencies. Request "
           "USDKRW, USDCNY/CNH, USDBRL, USDARS, USDNGN, USDVND before any further fx screening. "
           "Re-screening the majors would be breadth-mining the currencies the mechanism already "
           "predicts pay nothing. RUB is re-testable as a data/infra kill if the feed is restored."),
}


def main() -> None:
    summary = []
    for axis in AXES:
        p = OUT / f"{axis}.json"
        rep = json.loads(p.read_text("utf-8"))
        screened = [t for t in rep["trials"] if "verdict" in t and t.get("n")]
        axis_bar = _bar(len(screened))
        for t in screened:
            k = _step(t["name"])
            best = max(abs(t.get("sharpe_momentum", 0)), abs(t.get("sharpe_reversal", 0)))
            corr = round(best / math.sqrt(k), 2)
            t["period_days"] = k
            t["sharpe_best_reported"] = best
            t["sharpe_best_corrected"] = corr
            t["sharpe_correction_note"] = (
                "harness hardcodes sqrt(365); for k-day periods the correct factor is "
                f"sqrt(365/{k}), so reported Sharpe is inflated by sqrt({k})={round(math.sqrt(k),2)}x"
                if k > 1 else "1d periods -- harness annualization correct, no adjustment")
            tstat = round(abs(t.get("ic", 0)) * math.sqrt(max(t["n"] - 2, 1)), 2)
            t["ic_t_stat"] = tstat
            t["clears_axis_multiplicity_bar"] = bool(tstat > axis_bar)
            t["clears_campaign_multiplicity_bar"] = bool(tstat > CAMPAIGN_BAR)
            # Controls and future-peeking diagnostics can NEVER be candidates, however they score.
            # SHIFT_*_plus1d feeds the signal from the FUTURE; a strong score there is evidence of
            # contemporaneous co-movement (an ARTIFACT), which rule 8 says is never an edge.
            nm = t["name"]
            is_ctrl = ("DENOM-CONTROL" in nm or "LOOKAHEAD-CONTROL" in nm
                       or "SHIFT_" in nm or "_LAG1d" in nm)
            if is_ctrl:
                kind = ("future-peeking shift diagnostic" if "plus1d" in nm else
                        "denomination artifact control" if "DENOM-CONTROL" in nm else
                        "look-ahead control" if "LOOKAHEAD-CONTROL" in nm else
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
                               "campaign_trials": TOTAL_TRIALS, "campaign_bonferroni_t": CAMPAIGN_BAR}
        rep["verdict"] = VERDICTS[axis]
        rep["forward_clock"] = "NO -- no construction survived; Stage A has zero promotion authority"
        rep["next_step"] = NEXT[axis]
        p.write_text(json.dumps(rep, indent=1, default=str), "utf-8")

        surv = [t for t in screened if t["verdict_adjusted"].startswith("SCREEN-INTERESTING")]
        summary.append((axis, len(screened), len(surv)))
        print(f"\n=== {axis}: {len(screened)} trials, {len(surv)} survive correction+multiplicity "
              f"(axis bar t>{axis_bar}, campaign t>{CAMPAIGN_BAR}) ===")
        for t in sorted(screened, key=lambda x: -abs(x.get("ic", 0)))[:5]:
            print(f"  {t['name']:46s} IC={t['ic']:+.4f} t={t['ic_t_stat']:.2f} "
                  f"Sh {t['sharpe_best_reported']:.2f}->{t['sharpe_best_corrected']:.2f}  "
                  f"{t['verdict_adjusted'][:58]}")
    print("\n", summary)


if __name__ == "__main__":
    main()
