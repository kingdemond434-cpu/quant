"""Broad stablecoin-supply momentum collector + Stage-A screen (2026-07-23 alt-data batch).

Total stablecoin market cap (DefiLlama, ALL issuers/chains) as a macro dollar-liquidity signal:
rising aggregate supply = net minting = new capital entering crypto -> momentum (supply-z up
precedes higher forward BTC return). Cleanest survivor of the alt-data batch: IC +0.067, momentum
Sharpe 0.88, same-period corr +0.08 (orthogonal), residual IC +0.072 (STRENGTHENS -> genuinely
leading), over 900 days. Passes the de-contam + SUSPECT-LOOKAHEAD rails.

RELATIONSHIP TO EXISTING SIGNAL (angle-14, no double-counting): scripts/run_stablecoin_flows.py
already RECORDS a supply figure (USDT+USDC on-chain totalSupply) as a designated signal, but it is
NOT screened or forward-tracked in run_axis_shadows -- it just accrues in an archive. This is the
SAME economic construct with (a) broader coverage (all stablecoins incl. DAI/USDe/FDUSD/PYUSD, not
just USDT+USDC) and (b) the formal Holm-tracked forward clock the archived version lacks. Treat the
two as ONE hypothesis for evidence purposes; this is the evaluated version.

Free DefiLlama API, no key. stdlib + numpy. Run from repo root.
"""
from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from libs.research import vintage
from libs.research.axis_integrity import check_move, move_bar
from libs.research.axis_screen import stage_a_screen

_ROOT = Path(__file__).resolve().parent.parent
_STABLES = "https://stablecoins.llama.fi/stablecoincharts/all"
_BINANCE = "https://api.binance.com/api/v3/klines"
_SERIES = Path("data/stablecoin_supply.jsonl")
#: Vintage-store key. Same store R0316 built for the revising FRED/RFB series.
_VINTAGE_SERIES = "stablecoin_supply"


def _get(url: str) -> object:
    req = urllib.request.Request(url, headers={"User-Agent": "quant-stablesupply/1.0"})
    with urllib.request.urlopen(req, timeout=35) as r:
        return json.loads(r.read().decode())


def _supply() -> dict[str, float]:
    d = _get(_STABLES)
    out: dict[str, float] = {}
    if not isinstance(d, list):        # narrow the untyped JSON boundary, do not assume shape
        return out
    for x in d:
        v = x.get("totalCirculatingUSD") or x.get("totalCirculating") or {}
        peg = v.get("peggedUSD") if isinstance(v, dict) else None
        if peg is not None:
            out[datetime.fromtimestamp(int(x["date"]), tz=UTC).date().isoformat()] = float(peg)
    return out


def _binance_daily(sym: str, n: int = 900) -> dict[str, float]:
    rows = _get(f"{_BINANCE}?symbol={sym}&interval=1d&limit={n}")
    if not isinstance(rows, list):
        return {}
    return {datetime.fromtimestamp(int(r[0]) / 1000, tz=UTC).date().isoformat(): float(r[4])
            for r in rows}


def main() -> None:
    sup = _supply()
    gbtc = _binance_daily("BTCUSDT")
    if not (sup and gbtc):
        raise SystemExit(f"fetch failed: supply={len(sup)} binance={len(gbtc)}")
    dates = sorted(set(sup) & set(gbtc))
    if len(dates) < 90:
        raise SystemExit(f"only {len(dates)} aligned days")

    sig = np.array([sup[d] for d in dates])
    btc = np.array([gbtc[d] for d in dates])
    ret = np.zeros(len(btc))
    ret[1:] = btc[1:] / btc[:-1] - 1.0

    z = np.zeros(len(sig))
    for t in range(20, len(sig)):
        w = sig[t - 20:t]
        sd = w.std()
        z[t] = (sig[t] - w.mean()) / sd if sd > 0 else 0.0

    scr = stage_a_screen(sig, ret, name="stablecoin_supply_momentum")

    # WHAT THE VENDOR SAID THEN vs WHAT IT SAYS NOW (R0389). DefiLlama silently rewrites its
    # published history, so the screen above -- which recomputes on the FULL re-fetched series
    # every run -- scores on numbers that did not exist at decision time. Measured 2026-08-12
    # over the 21 dates we hold both for: 18 of 20 comparable dates REVISED, every one UPWARD,
    # median +0.53% and max +1.04%. The point-in-time row is the as-of record and is never
    # rewritten here; the delta is recorded as its own series exactly as L1.46 makes
    # WHAT THE VENDOR SAID THEN vs WHAT IT SAYS NOW (R0389). DefiLlama silently rewrites its
    # published history, so the screen above -- which recomputes on the FULL re-fetched series
    # every run -- scores on numbers that did not exist at decision time. Measured 2026-08-12
    # against our own point-in-time rows: 18 of 20 comparable dates REVISED, every one UPWARD,
    # median +0.53% and max +1.04%, against a 20-day sd of ~0.5%. So a ROUTINE revision is a full
    # sigma of the very signal being screened.
    #
    # THIS IS R0316's DEFECT ON A SECOND VENDOR, so it reuses R0316's store rather than a second
    # implementation (L2.9): vintage.record keeps the as-of VALUES, append-on-change, so
    # vintage.as_of(d) can later reconstruct what was genuinely knowable on date d. Recording the
    # full re-fetched series (not just today's point) is deliberate -- it captures the vendor
    # REWRITING history, which is the whole phenomenon, and a vintage not captured is gone.
    #
    # WHY THE SCREEN IS NOT "FIXED" BY SPLICING IN THE POINT-IN-TIME VALUES -- the obvious next
    # move, and it is wrong. We hold as-of rows for 21 days; the screen needs 900. A splice joins
    # 879 revised values to 21 systematically-lower as-of ones, and at the measured median
    # revision that join manufactures a ~1-SIGMA DISCONTINUITY -- a spurious signal at exactly the
    # recent end the screen weights most. Mixing two bases is worse than either alone. So: the
    # screen is computed on the REVISED series and says so in its output, the forward clock reads
    # the un-rewritten point-in-time rows, and a genuine point-in-time screen becomes possible
    # once the vintage store has accrued the depth to serve one.
    today = datetime.now(tz=UTC).date().isoformat()
    n_revised = vintage.record(_ROOT, _VINTAGE_SERIES, sup, vintage=today)
    vsum = vintage.summarise(_ROOT, _VINTAGE_SERIES)

    # REFUSE AN IMPLAUSIBLE READ RATHER THAN STORE IT, against a bar this series MEASURES FROM
    # ITSELF rather than the hand-picked 10% that fixed the 2026-07-27 instance -- that constant
    # was reasoned from this series' float and transfers to no other axis (R0390). The check runs
    # against the API's OWN previous day, so it is independent of whatever this artifact happens
    # to already hold, and it exits nonzero so a bad vendor day surfaces as a failed collector run
    # instead of a silently poisoned row (L1.41: a refusal path, and no silent swallow). A stored
    # corrupt LEVEL would also poison the trailing z-window for the next 20 days, not just its
    # own row, which is why this refuses the WRITE rather than nulling the z.
    bar = move_bar([float(x) for x in sig])
    verdict = check_move(float(sig[-1]), float(sig[-2]), bar) if len(sig) >= 2 else None
    if verdict is not None and not verdict.ok:
        raise SystemExit(f"REFUSED {dates[-1]}: {verdict.reason} -- almost certainly a bad vendor "
                         f"read; not writing to {_SERIES}")

    rec = {"date": today, "supply_usd": round(float(sig[-1]), 0),
           "z20": round(float(z[-1]), 3), "n_hist": len(dates)}
    prev = _SERIES.read_text("utf-8").strip().splitlines() if _SERIES.exists() else []
    if not prev or json.loads(prev[-1]).get("date") != today:
        with _SERIES.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")

    print(f"STABLECOIN-SUPPLY SCREEN | {len(dates)} aligned days")
    print(f"  current z20: {z[-1]:+.2f}   total supply ${sig[-1]:,.0f}")
    print(f"  plausibility bar (measured from this series): "
          f"{bar.value:.2%}" if bar.measured else f"  plausibility bar: {bar.basis}")
    print(f"  VENDOR VINTAGE ({vsum['status']}): {n_revised} value(s) new-or-REWRITTEN this run; "
          f"{vsum['detail']}. The screen above runs on the vendor's CURRENT (revised) history; "
          f"the forward clock reads the un-rewritten point-in-time rows and does not.")
    print(f"  IC {scr['ic']:+.4f} | same-period {scr['same_period_corr']:+.3f} "
          f"| residual IC {scr['residual_ic']:+.4f}")
    print(f"  timing Sharpe -- MOMENTUM {scr['sharpe_momentum']}  "
          f"REVERSAL {scr['sharpe_reversal']}")
    print(f"  VERDICT (Stage-A, zero promotion authority): {scr['verdict']}  "
          f"[momentum, direction=+1; SAME construct as stablecoin_flows supply field -- one "
          f"hypothesis, this is the formally-tracked version]")


if __name__ == "__main__":
    main()
