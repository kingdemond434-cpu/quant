"""Stage-A screen: WIKIPEDIA PAGEVIEW ATTENTION vs crypto forward returns.

MECHANISM (pre-registered before compute, 2026-07-26): retail attention is the front of the
reflexive inflow loop. A person who does not yet own crypto must first LOOK IT UP; the lookup
precedes the account, the account precedes the deposit, the deposit precedes the bid. Wikipedia
pageviews measure that lookup directly, with no keyword-ambiguity and no sampling (unlike Google
Trends, which is a normalised index).

WHAT IS ALREADY DEAD AND IS **NOT** RE-RUN HERE
-----------------------------------------------
graveyard.md: `multilingual_wikipedia_attention (en/ja/ko/ru/zh BTC pageviews)` -- all 5
SCREEN-WEAK, tag `no_edge_daily`, lesson "attention co-moves with, does not lead, daily returns
... Kills the whole multilingual-search-trends category as a daily timing signal". Therefore the
construction "Bitcoin-article pageviews -> next-day ABSOLUTE BTC return" IS GRAVEYARDED AND IS
SKIPPED. It is not re-screened at any language, including English. Re-testing it would burn DSR
budget twice on a settled question.

WHAT IS MATERIALLY NEW (and why it is not the graveyarded hypothesis)
--------------------------------------------------------------------
W1 GATEWAY/ONBOARDING ATTENTION -- a DIFFERENT OBJECT, not a different language. The dead test
   measured attention to the ASSET ("Bitcoin"), which is news-reading and is coincident with
   price by construction (you read about bitcoin because it moved). W1 measures attention to the
   ACCESS RAILS -- "Coinbase" + "Binance" + "Cryptocurrency" -- i.e. someone asking *how do I buy
   this*, not *what just happened*. Purchase-intent lookups should LEAD deposits, whereas
   news-reading LAGS the print. This is the mechanism arm the dead test never isolated.
   Target: ABSOLUTE BTC return (onboarding flow is market-wide). Horizons 1d/5d/20d -- account
   opening and fiat settlement take days-to-weeks, so 20d is mechanism-appropriate here.

W2 CROSS-SECTIONAL RELATIVE ATTENTION -- a DIFFERENT TARGET. The dead test asked "does attention
   time the market". W2 asks "does attention pick the horse": for asset A, does A's pageview
   share vs Bitcoin's predict A's return RELATIVE TO Bitcoin. Retail attention is a rivalrous,
   near-fixed budget; the marginal retail dollar goes to whatever is being looked up, so
   attention should be an ASSET-SELECTION signal even where it is not a timing signal. Rule 5
   requires the mechanism-appropriate target, and for a selection mechanism that is the
   cross-sectional relative return, never the absolute one. Assets: ETH, SOL, DOGE (each has
   its own page and its own USDT pair). Horizons 1d/5d only -- retail attention decays in days,
   so a 20d hold is mechanism-inappropriate and is deliberately NOT run.

TIMESTAMP ALIGNMENT (declared) + LOOK-AHEAD FLAG
------------------------------------------------
  * Wikimedia Pageviews API `daily` granularity stamps YYYYMMDD00 and counts the COMPLETE UTC
    calendar day [00:00, 24:00). So pageview day t covers exactly the same UTC window as the
    Binance D1 bar for day t.
  * That means the count for day t is FINAL only at 24:00 UTC day t -- the same instant as the
    crypto close of day t -- and Wikimedia publishes it with a ~45-60min lag, so it is really in
    hand ~01:00 UTC on day t+1.
  * stage_a_screen predicts ret[t+1] (the 00:00->24:00 UTC day t+1 return) from signal[t].
    Entering at 00:00 UTC t+1 would use a number that is not published until ~01:00 UTC t+1.
    THIS IS A REAL, DECLARED ~1h LOOK-AHEAD -- roughly 4% of the holding period.
  * MITIGATION (run, not asserted): every construction is ALSO run in a conservative +1d-lagged
    form (signal[t-1] -> ret[t+1]), which is unambiguously knowable at entry. If a result does
    not survive the lag, the result was the 1h leak.

TRIALS (13, all pre-declared, all logged): W1 x {1d,5d,20d} = 3; W1 lagged x {1d} = 1;
W2 x {ETH,SOL,DOGE} x {1d,5d} = 6; W2 lagged x {ETH,SOL,DOGE} x {1d} = 3.
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

WIKI = ROOT / "data" / "lake" / "bronze" / "wikipedia"
OUT = ROOT / "reports" / "axis_screens"


def _views(article: str) -> pd.Series:
    items = json.loads((WIKI / f"{article}_daily.json").read_text("utf-8"))["items"]
    s = pd.Series({pd.Timestamp(i["timestamp"][:8], tz="UTC"): float(i["views"]) for i in items})
    return s.sort_index()


def _close(sym: str) -> pd.Series:
    fs = sorted((ROOT / f"data/lake/bronze/crypto/{sym}/D1").glob("year=*/month=*/part-0.parquet"))
    df = pd.concat([pd.read_parquet(f) for f in fs])
    df["day"] = pd.to_datetime(df["timestamp"], utc=True).dt.floor("D")
    return df.sort_values("day").drop_duplicates("day").set_index("day")["close"]


def _ds_pair(sig: np.ndarray, ra: np.ndarray, rb: np.ndarray, step: int):
    """Non-overlapping downsample; relative return compounded PER LEG then differenced."""
    n = len(sig) // step
    s = np.array([sig[i * step] for i in range(n)])
    r = np.array([float(np.prod(1 + ra[i * step:(i + 1) * step])
                        - np.prod(1 + rb[i * step:(i + 1) * step])) for i in range(n)])
    return s, r


def main() -> None:
    trials: list[dict] = []
    skipped = [{
        "name": "bitcoin_article_pageviews->btc_absolute_1d",
        "verdict": "NOT-RUN (GRAVEYARDED)",
        "reason": "graveyard.md multilingual_wikipedia_attention: en/ja/ko/ru/zh BTC pageviews all "
                  "SCREEN-WEAK, tag no_edge_daily, 'do not re-test as daily alpha'. English is one "
                  "of the five already killed. Not re-screened at any horizon or language.",
    }]

    # ---------- W1: gateway / onboarding attention -> ABSOLUTE BTC return ----------
    gate = (_views("Coinbase") + _views("Binance") + _views("Cryptocurrency")).dropna()
    btc = _close("BTCUSDT")
    d1 = pd.DataFrame({"gate": np.log(gate), "px": btc}).dropna()
    d1["ret"] = d1["px"].pct_change()
    d1 = d1.dropna()
    sig, ret = d1["gate"].to_numpy(), d1["ret"].to_numpy()
    trials.append(stage_a_screen(sig, ret, name="gateway_attention->btc_1d"))
    for step, zw in ((5, 12), (20, 6)):
        n = len(sig) // step
        s_d = np.array([sig[i * step] for i in range(n)])
        r_d = np.array([float(np.prod(1 + ret[i * step:(i + 1) * step]) - 1) for i in range(n)])
        trials.append(stage_a_screen(s_d, r_d, name=f"gateway_attention->btc_{step}d", zwin=zw))
    trials.append(stage_a_screen(sig[:-1], ret[1:], name="gateway_attention_LAG1d->btc_1d"))

    # ---------- W2: cross-sectional relative attention -> RELATIVE return ----------
    for art, sym in (("Ethereum", "ETHUSDT"), ("Solana", "SOLUSDT"), ("Dogecoin", "DOGEUSDT")):
        va, vb, pa, pb = _views(art), _views("Bitcoin"), _close(sym), btc
        d = pd.DataFrame({"va": va, "vb": vb, "pa": pa, "pb": pb}).dropna()
        d = d[(d["va"] > 0) & (d["vb"] > 0)]
        d["sig"] = np.log(d["va"]) - np.log(d["vb"])
        d["ra"], d["rb"] = d["pa"].pct_change(), d["pb"].pct_change()
        d = d.dropna()
        s, ra, rb = d["sig"].to_numpy(), d["ra"].to_numpy(), d["rb"].to_numpy()
        rel = ra - rb
        tag = art.lower()[:3]
        trials.append(stage_a_screen(s, rel, name=f"rel_attention_{tag}_vs_btc->rel_1d"))
        s5, r5 = _ds_pair(s, ra, rb, 5)
        trials.append(stage_a_screen(s5, r5, name=f"rel_attention_{tag}_vs_btc->rel_5d", zwin=12))
        trials.append(stage_a_screen(s[:-1], rel[1:],
                                     name=f"rel_attention_{tag}_vs_btc_LAG1d->rel_1d"))

    out = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "axis": "wikipedia",
        "n_days_gateway": len(d1),
        "range": [str(d1.index.min().date()), str(d1.index.max().date())],
        "alignment": (
            "Wikimedia daily pageviews stamp YYYYMMDD00 and count "
            "the COMPLETE UTC day [00:00,24:00) "
            "-- the same window as the Binance D1 bar for day t. Count for day t is final only at "
            "24:00 UTC t and published ~45-60min later, so signal[t]->ret[t+1] carries a DECLARED "
            "~1h look-ahead (~4% of the 1d holding period). Every construction is therefore ALSO "
            "run +1d-lagged (signal[t-1]->ret[t+1]), "
            "which is unambiguously knowable; a result that "
            "dies under the lag WAS the leak. 5d/20d NON-OVERLAPPING; relative returns compounded "
            "per leg then differenced."
        ),
        "skipped_graveyarded": skipped,
        "trials": trials,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "wikipedia.json").write_text(json.dumps(out, indent=1, default=str), "utf-8")
    for t in trials:
        print(f"{t['name']:46s} {t.get('verdict'):20s} IC={t.get('ic')} "
              f"shM={t.get('sharpe_momentum')} shR={t.get('sharpe_reversal')} "
              f"same={t.get('same_period_corr')} resIC={t.get('residual_ic')} n={t.get('n')}")


if __name__ == "__main__":
    main()
