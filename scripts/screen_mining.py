"""Stage-A screen: BITCOIN MINER ECONOMICS (hashrate / difficulty / revenue) vs BTC forward returns.

MECHANISM (pre-registered before compute, 2026-07-26): miners are the only structurally-forced
sellers in bitcoin. They carry USD-denominated fixed costs (power, hosting, debt service) against
a BTC-denominated revenue stream, and they cannot hedge the whole book. When revenue per unit of
hash (hashprice) falls below the marginal miner's cash cost, that cohort must (a) liquidate
treasury BTC to meet fiat obligations and (b) eventually power off. The power-off is OBSERVABLE
in the hashrate before it is observable in price. So a sustained hashrate roll-over ("capitulation")
marks a cohort of forced sellers being flushed OUT of the market; once they are gone the marginal
supply overhang is removed. PRE-REGISTERED SIGN: capitulation (ribbon < 0, difficulty cut) should
be FOLLOWED BY higher returns -> we expect NEGATIVE IC (reversal-positive Sharpe). If the sign
comes out positive we do NOT flip it and call it momentum (that is the xsec_lowvol p-hack the
graveyard names).

WHY THIS IS SLOW: rig power-off, hosting-contract termination and treasury liquidation run on
weeks, not hours. The mechanism-appropriate horizons are 5d and 20d; 1d is included only as the
standard control and is expected to be weak.

TIMESTAMP ALIGNMENT (declared):
  * blockchain.com daily chart points are stamped 00:00 UTC and carry the network state measured
    over that UTC day; the value for day t is complete only at the END of UTC day t.
  * stage_a_screen predicts target ret[t+1] from signal[t], so every signal is >=24h old at entry.
    NO look-ahead.
  * DIFFICULTY IS NOT A DAILY SERIES. It re-targets every 2016 blocks (~14d, IRREGULAR). The daily
    CSV is a STEP FUNCTION that stale-repeats inside an epoch (verified: last 5 rows identical to
    8 significant figures). A 20d z-score of the LEVEL is therefore degenerate, so the difficulty
    construction uses the 14d LOG-CHANGE, which is non-zero only when an adjustment has actually
    printed. Stale-repeat is not look-ahead (it is the last knowable value) but it does make the
    series autocorrelated -- declared.
  * HASHRATE IS AN ESTIMATE, not a measurement: it is inferred from blocks-found in a trailing
    window and is Poisson-noisy (verified: 17% day-over-day swings). The 30/60d ribbon is the
    noise-appropriate construction; raw daily hashrate is mostly block-luck.
  * Target = BTC absolute (timing) return. Miner forced-selling is a MARKET-WIDE supply flow, not
    an asset-selection signal, so absolute return is the mechanism-appropriate target (rule 5).

CONTAMINATION PRE-REGISTRATION (the cm_mvrv lesson): miners-revenue is quoted in USD and equals
(BTC issued x BTC price) + fees, so ANY ratio built on it has BTC PRICE IN THE NUMERATOR and its
20d z-score is recent price momentum wearing a costume. M3 (USD hashprice) is therefore PREDICTED
to fail the angle-20 de-contamination gate. M4 is the analytically de-contaminated twin: dividing
revenue by BTC close converts it to BTC-denominated revenue, removing the price factor, exactly as
the graveyard prescribes ("orthogonalize FIRST or screen at the mechanism's native horizon").
M3 is retained and reported anyway -- confirming a pre-registered failure is a first-class result.

TRIALS (12, all pre-declared, all logged whether they print or not):
  M1 hash_ribbon(30/60)          -> BTC 1d, 5d, 20d
  M2 difficulty 14d log-change   -> BTC 1d, 5d, 20d
  M3 hashprice USD (rev/hash)    -> BTC 1d, 5d, 20d   [contamination expected]
  M4 hashprice BTC (rev_btc/hash)-> BTC 1d, 5d, 20d   [de-contaminated twin of M3]
MULTIPLICITY IS DECLARED: at the harness floors (|IC|>=0.03, Sharpe>=0.5) roughly one nominal
pass in 12 is the chance expectation, so a lone SCREEN-INTERESTING here is NOT evidence.

Stage A only -- ZERO promotion authority. A survivor earns a pre-registered forward clock.
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

MINE = ROOT / "data" / "lake" / "bronze" / "mining"
OUT = ROOT / "reports" / "axis_screens"


def _series(name: str) -> pd.Series:
    d = pd.read_csv(MINE / f"{name}.csv", header=None, names=["ts", "v"], parse_dates=["ts"])
    d["ts"] = pd.to_datetime(d["ts"], utc=True).dt.floor("D")
    return d.set_index("ts")["v"].sort_index()


def _btc() -> pd.Series:
    fs = sorted((ROOT / "data/lake/bronze/crypto/BTCUSDT/D1").glob("year=*/month=*/part-0.parquet"))
    df = pd.concat([pd.read_parquet(f) for f in fs])
    df["day"] = pd.to_datetime(df["timestamp"], utc=True).dt.floor("D")
    return df.sort_values("day").drop_duplicates("day").set_index("day")["close"]


def _downsample(sig: np.ndarray, ret_1d: np.ndarray, step: int) -> tuple[np.ndarray, np.ndarray]:
    """Non-overlapping step-day periods: signal at period start, compounded period return."""
    n = len(sig) // step
    s = np.array([sig[i * step] for i in range(n)])
    r = np.array([float(np.prod(1.0 + ret_1d[i * step:(i + 1) * step]) - 1.0) for i in range(n)])
    return s, r


def main() -> None:
    hr, diff, rev, px = (_series("hash-rate"), _series("difficulty"),
                         _series("miners-revenue"), _btc())
    df = pd.DataFrame({"hr": hr, "diff": diff, "rev": rev, "px": px}).dropna()
    df = df[df["hr"] > 0]
    df["ret_1d"] = df["px"].pct_change()

    # M1 hash ribbon: 30d vs 60d MA of the (Poisson-noisy) hashrate estimate
    df["m1_ribbon"] = df["hr"].rolling(30).mean() / df["hr"].rolling(60).mean() - 1.0
    # M2 difficulty 14d log-change -- non-zero only when a ~2016-block retarget has printed
    df["m2_diffchg"] = np.log(df["diff"]).diff(14)
    # M3 USD hashprice -- PRICE IN NUMERATOR, contamination pre-registered
    df["m3_hp_usd"] = df["rev"] / df["hr"]
    # M4 BTC-denominated hashprice -- price factor divided out (de-contaminated twin)
    df["m4_hp_btc"] = (df["rev"] / df["px"]) / df["hr"]

    df = df.dropna()
    ret = df["ret_1d"].to_numpy()
    trials = []
    for col, label in (("m1_ribbon", "hash_ribbon_30_60"), ("m2_diffchg", "difficulty_14d_logchg"),
                       ("m3_hp_usd", "hashprice_usd"), ("m4_hp_btc", "hashprice_btc_denom")):
        sig = df[col].to_numpy()
        trials.append(stage_a_screen(sig, ret, name=f"{label}->btc_1d"))
        for step, zw in ((5, 12), (20, 6)):
            s_d, r_d = _downsample(sig, ret, step)
            trials.append(stage_a_screen(s_d, r_d, name=f"{label}->btc_{step}d", zwin=zw))

    out = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "axis": "mining",
        "n_days": len(df),
        "range": [str(df.index.min().date()), str(df.index.max().date())],
        "alignment": (
            "blockchain.com daily points stamped 00:00 UTC carry the network state of that whole "
            "UTC day; signal[t] predicts BTC close-to-close ret[t+1], so >=24h old at entry -- NO "
            "look-ahead. Difficulty is NOT daily (retargets ~2016 blocks/~14d, irregular): the "
            "daily CSV stale-repeats inside an epoch, so the LEVEL z-score is degenerate and the "
            "14d log-change is used instead. Hashrate is a Poisson-noisy trailing block-count "
            "estimate (~17% d/d swings), hence the 30/60 ribbon. 5d/20d are NON-OVERLAPPING."
        ),
        "trials": trials,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "mining.json").write_text(json.dumps(out, indent=1, default=str), "utf-8")
    for t in trials:
        print(f"{t['name']:42s} {t.get('verdict'):20s} IC={t.get('ic')} "
              f"shM={t.get('sharpe_momentum')} shR={t.get('sharpe_reversal')} "
              f"same={t.get('same_period_corr')} resIC={t.get('residual_ic')} n={t.get('n')}")


if __name__ == "__main__":
    main()
