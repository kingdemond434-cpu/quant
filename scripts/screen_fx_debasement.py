"""Stage-A screen: FX DEBASEMENT / CAPITAL-CONTROL DEMAND vs BTC forward returns.

MECHANISM (pre-registered before compute, 2026-07-26): bitcoin's oldest non-speculative bid is
ESCAPE DEMAND. A holder of a currency that is losing purchasing power, or who is fenced in by
capital controls, buys a bearer asset that settles outside the domestic banking rail. The desk has
already proven this family pays: kimchi premium screened IC +0.148 and is on a live forward clock.

THE HARD CONSTRAINT ON THIS AXIS (found before screening, and it is the headline)
--------------------------------------------------------------------------------
The ingested fx lake holds 57 crosses and NOT ONE of the currencies whose barrier height actually
drives the proven mechanism: NO KRW, NO CNY/CNH, NO BRL, NO ARS, NO NGN, NO VND, NO EGP, NO INR.
The graveyard's own era-evidence entry (`era_crossvenue_fiat_premium_arb`) states the governing
law: "premium magnitude tracks BARRIER HEIGHT". Every high-barrier currency is absent. What is
present is majors plus three freely-floating EM crosses. So this axis, AS INGESTED, cannot express
the mechanism that made fx high-prior -- it can only test the weak-barrier tail of it.

WHAT IS ALREADY DEAD AND IS **NOT** RE-RUN HERE (graveyard.md + web/axis_shadows.json)
-------------------------------------------------------------------------------------
  * try_premium_timing (Turkey venue premium)   -- `timing_artifact`, de-contam corr -0.495. SKIPPED.
  * coinbase_premium_timing                     -- `timing_artifact`, contam +0.256. SKIPPED.
  * bithumb_kr_premium                          -- `lookahead_artifact`, KST candle. SKIPPED.
  * coinone_kr_premium                          -- `redundant` with kimchi. SKIPPED.
  * bitbank_jp / mercado_br premiums            -- `no_economics`/`weak`. SKIPPED.
  * kimchi_premium, cny_premium                 -- LIVE forward clocks (axis_shadows.json,
                                                   ACCRUING). Re-screening a running clock is
                                                   forbidden and would double-spend DSR. SKIPPED.
NOTE: none of the above is even constructible from this lake (no crypto venue prices in it, and
no KRW/CNY at all). The skip list is therefore belt-and-braces, not a near miss.

WHAT IS MATERIALLY NEW: this is a PURE-FX macro construction, not a venue premium. It contains no
crypto venue price on either side, so it cannot reproduce the close-timestamp microstructure
artifact that killed the Turkey and Coinbase premiums -- those died because a near-zero-variance
venue spread was dominated by FX-close-timing noise. Here the FX move IS the signal, not a
contaminant of one. Adjacency to the dead try_premium is DECLARED: TRY appears in F3, but as a
depreciation rate, not as a crypto premium.

TIMESTAMP ALIGNMENT (declared) -- THE PRIMARY ARTIFACT HAZARD ON THIS AXIS
--------------------------------------------------------------------------
  * Verified empirically: fx D1 bars carry Mon-Fri labels only, zero Sat/Sun rows. The FX week's
    Sunday 21:00 UTC open is folded into the Monday bar, so a bar labelled day t is the SESSION of
    day t, closing ~21:00-22:00 UTC on day t.
  * The crypto D1 bar for day t closes at 24:00 UTC on day t. So the FX close PRECEDES the crypto
    close of the SAME label by ~2-3h. signal[t] -> crypto ret[t+1] therefore uses a value ~3h old
    at entry and ~27h old at exit: CONSERVATIVELY NO LOOK-AHEAD. The dangerous direction (crypto
    leading FX) is not the one screened.
  * WEEKENDS: FX is closed Sat/Sun. FX is reindexed onto the crypto 7-day UTC calendar with
    FORWARD-FILL of the last knowable close (Friday's close carries through the weekend). This is
    exactly what a live trader holds -- not look-ahead -- but it stale-repeats 2/7 of all days and
    inflates signal autocorrelation. DECLARED.
  * STALENESS: the fx lake ends 2026-06-05 (EM crosses) / 2026-06-19 (majors) while crypto runs to
    2026-07-26. The screen sample therefore stops at the FX end, ~7 weeks short of today.
  * SHIFT SENSITIVITY (rule 8, the bithumb lesson): the headline construction is re-run at -1d and
    +1d. A genuine lead decays away from its true lag; an artifact holds its |IC| under shifting.

TRIALS (13, all pre-declared, all logged):
  F1 EM debasement basket (TRY,ZAR,MXN 20d depreciation vs USD) -> BTC/USDT 1d, 5d, 20d
  F2 synthetic DXY 20d change                                   -> BTC/USDT 1d, 5d, 20d
  F3 TRY-only 20d depreciation                                  -> BTC/USDT 1d, 5d
  F4 DENOMINATION CONTROL: F1 -> BTC priced IN TRY              -> 1d, 5d   [artifact probe]
  F5 shift sensitivity on F1                                    -> -1d, +1d
RUB IS EXCLUDED WITH CAUSE: the EURRUB feed terminates 2022-02-28 (sanctions cut). That is a
`data/infra` exclusion, not an economic one -- RUB is re-testable if the feed is ever restored.

Stage A only -- ZERO promotion authority.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from libs.research.axis_screen import stage_a_screen  # noqa: E402

FX = ROOT / "data" / "lake" / "bronze" / "fx"
OUT = ROOT / "reports" / "axis_screens"


def _fx(pair: str) -> pd.Series:
    fs = sorted((FX / pair / "D1").glob("year=*/month=*/part-0.parquet"))
    df = pd.concat([pd.read_parquet(f) for f in fs])
    df["day"] = pd.to_datetime(df["timestamp"], utc=True).dt.floor("D")
    return df.sort_values("day").drop_duplicates("day").set_index("day")["close"]


def _btc() -> pd.Series:
    fs = sorted((ROOT / "data/lake/bronze/crypto/BTCUSDT/D1").glob("year=*/month=*/part-0.parquet"))
    df = pd.concat([pd.read_parquet(f) for f in fs])
    df["day"] = pd.to_datetime(df["timestamp"], utc=True).dt.floor("D")
    return df.sort_values("day").drop_duplicates("day").set_index("day")["close"]


def _ds(sig: np.ndarray, ret: np.ndarray, step: int):
    n = len(sig) // step
    s = np.array([sig[i * step] for i in range(n)])
    r = np.array([float(np.prod(1 + ret[i * step:(i + 1) * step]) - 1) for i in range(n)])
    return s, r


def main() -> None:
    eurusd = _fx("EURUSD")
    # USD-per-unit -> quote as UNITS PER USD so that a RISE = local currency WEAKENING
    usdtry = _fx("EURTRY") / eurusd
    usdzar = _fx("EURZAR") / eurusd
    usdmxn = _fx("EURMXN") / eurusd
    usdsek = _fx("EURSEK") / eurusd
    dxy = (np.log(50.14348112)
           - 0.576 * np.log(eurusd) + 0.136 * np.log(_fx("USDJPY"))
           - 0.119 * np.log(_fx("GBPUSD")) + 0.091 * np.log(_fx("USDCAD"))
           + 0.042 * np.log(usdsek) + 0.036 * np.log(_fx("USDCHF")))

    btc = _btc()
    idx = btc.index                                    # crypto 7-day UTC calendar is the master
    fxd = pd.DataFrame({"try_": usdtry, "zar": usdzar, "mxn": usdmxn, "dxy": dxy})
    fxd = fxd.reindex(idx.union(fxd.index)).sort_index().ffill().reindex(idx)   # last knowable

    d = pd.DataFrame({"px": btc}).join(fxd).dropna()
    d["ret"] = d["px"].pct_change()
    # 20d log depreciation of each EM currency (rise in units-per-USD = weakening)
    for c in ("try_", "zar", "mxn"):
        d[f"dep_{c}"] = np.log(d[c]).diff(20)
    d["f1_basket"] = d[["dep_try_", "dep_zar", "dep_mxn"]].mean(axis=1)
    d["f2_dxy"] = d["dxy"].diff(20)
    d["f3_try"] = d["dep_try_"]
    # F4 denomination control: BTC priced in TRY -> its return contains the TRY move mechanically
    d["ret_btc_in_try"] = (d["px"] * d["try_"]).pct_change()
    d = d.dropna()

    ret, ret_try = d["ret"].to_numpy(), d["ret_btc_in_try"].to_numpy()
    trials: list[dict] = []
    skipped = [
        {"name": n, "verdict": "NOT-RUN (GRAVEYARDED)", "reason": r} for n, r in (
            ("try_premium_timing", "graveyard `timing_artifact`, de-contam -0.495"),
            ("coinbase_premium_timing", "graveyard `timing_artifact`, contam +0.256"),
            ("bithumb_kr_premium", "graveyard `lookahead_artifact` (KST candle label)"),
            ("coinone_kr_premium", "graveyard `redundant` with kimchi"),
            ("bitbank_jp_premium / mercado_br_premium", "graveyard `no_economics`/`weak`"),
        )] + [
        {"name": n, "verdict": "NOT-RUN (LIVE FORWARD CLOCK)", "reason": r} for n, r in (
            ("kimchi_premium", "axis_shadows.json ACCRUING -- re-screening double-spends DSR"),
            ("cny_premium", "axis_shadows.json ACCRUING -- re-screening double-spends DSR"),
        )]

    for col, label in (("f1_basket", "em_debasement_basket_try_zar_mxn"),
                       ("f2_dxy", "synthetic_dxy_20d_chg")):
        sig = d[col].to_numpy()
        trials.append(stage_a_screen(sig, ret, name=f"{label}->btc_1d"))
        for step, zw in ((5, 12), (20, 6)):
            s_d, r_d = _ds(sig, ret, step)
            trials.append(stage_a_screen(s_d, r_d, name=f"{label}->btc_{step}d", zwin=zw))

    s3 = d["f3_try"].to_numpy()
    trials.append(stage_a_screen(s3, ret, name="try_depreciation_20d->btc_1d"))
    s3d, r3d = _ds(s3, ret, 5)
    trials.append(stage_a_screen(s3d, r3d, name="try_depreciation_20d->btc_5d", zwin=12))

    # F4 denomination artifact control
    s1 = d["f1_basket"].to_numpy()
    trials.append(stage_a_screen(s1, ret_try, name="DENOM-CONTROL_em_basket->btc_IN_TRY_1d"))
    s4d, r4d = _ds(s1, ret_try, 5)
    trials.append(stage_a_screen(s4d, r4d, name="DENOM-CONTROL_em_basket->btc_IN_TRY_5d", zwin=12))

    # F5 shift sensitivity on F1 (rule 8)
    trials.append(stage_a_screen(s1[:-1], ret[1:], name="SHIFT_em_basket_minus1d->btc_1d"))
    trials.append(stage_a_screen(s1[1:], ret[:-1], name="SHIFT_em_basket_plus1d->btc_1d"))

    out = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "axis": "fx",
        "n_days": len(d),
        "range": [str(d.index.min().date()), str(d.index.max().date())],
        "coverage_gap": ("fx lake has 57 crosses but NONE of the high-barrier currencies that drive "
                         "the proven mechanism: no KRW, CNY/CNH, BRL, ARS, NGN, VND, EGP, INR. "
                         "EURRUB feed terminates 2022-02-28 (sanctions) -> RUB excluded as "
                         "data/infra, re-testable if restored."),
        "alignment": (
            "fx D1 bars are Mon-Fri only (verified: zero Sat/Sun rows), labelled at the SESSION "
            "date, closing ~21:00-22:00 UTC on that date -- i.e. ~2-3h BEFORE the crypto 24:00 UTC "
            "close of the same label. signal[t]->crypto ret[t+1] is ~3h old at entry: NO look-ahead. "
            "FX reindexed onto the crypto 7-day UTC calendar with FORWARD-FILL of the last knowable "
            "close (stale-repeats 2/7 of days; declared). Sample ends at the FX lake end "
            "(2026-06-05 EM / 2026-06-19 majors), ~7wk short of the crypto lake. 5d/20d "
            "NON-OVERLAPPING. Shift sensitivity -1d/+1d run per rule 8."),
        "skipped_graveyarded": skipped,
        "trials": trials,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "fx.json").write_text(json.dumps(out, indent=1, default=str), "utf-8")
    for t in trials:
        print(f"{t['name']:48s} {t.get('verdict'):20s} IC={t.get('ic')} "
              f"shM={t.get('sharpe_momentum')} shR={t.get('sharpe_reversal')} "
              f"same={t.get('same_period_corr')} resIC={t.get('residual_ic')} n={t.get('n')}")


if __name__ == "__main__":
    main()
