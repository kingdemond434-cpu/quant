"""Stage-A screen: US SPOT-BITCOIN ETF NET FLOWS vs BTC forward returns.

MECHANISM (pre-registered before compute, 2026-07-26): a US spot-ETF creation is a hard,
non-discretionary spot purchase. When an AP creates a basket, the sponsor must acquire real BTC
and move it to the custodian -- unlike perp/futures demand, this flow cannot be netted internally
and it removes float from the exchange-tradeable supply. It is also the only clean read the desk
has on the REGULATED ALLOCATOR cohort (RIAs, model portfolios, wirehouse platforms), whose
rebalancing is slow, calendar-driven and persistent rather than mean-reverting. Persistent
allocator demand should therefore push price over days, not minutes -- so the mechanism-appropriate
horizons are 5d and 20d, with 1d as a control.

TIMESTAMP ALIGNMENT (declared) -- AND WHY THE OBVIOUS BUILD IS LOOK-AHEAD
------------------------------------------------------------------------
  * Farside reports NET FLOW per ETF for a US TRADING day t. US business days only: no weekends,
    no US market holidays. The crypto target trades 7 days a week, so the two calendars differ.
  * PUBLICATION LAG IS REAL AND MATTERS. ETF creations settle T+1 and the flow table for day t is
    not published until the EVENING of day t+1. Therefore flow[t] is NOT knowable at the crypto
    close of day t, and it is NOT knowable at the open of day t+1 either.
  * The naive build -- signal flow[t] -> BTC ret[t+1], which is what stage_a_screen computes by
    default -- IS LOOK-AHEAD. It trades day t+1 using a number published at the END of day t+1.
  * CORRECT BUILD, implemented here: the flow series is lagged ONE EXTRA DAY before being handed
    to the harness, so the harness's own t->t+1 step lands on flow[t] -> BTC ret[t+2]. The signal
    is then ~24h published and unambiguously knowable at entry.
  * BOTH are run and BOTH are logged -- the naive one is retained explicitly as a LOOK-AHEAD
    CONTROL, never as a candidate. If the naive build scores materially better than the correct
    one, that gap IS the leak, and it is reported as an artifact rather than an edge.
  * Target = BTC absolute (timing) return: ETF creation is a market-wide supply/demand flow, not
    an asset-selection signal.

DATA SUFFICIENCY (checked BEFORE screening -- this is the finding)
-----------------------------------------------------------------
The bronze layer holds TWO Farside HTML snapshots. Farside's page serves only a TRAILING WINDOW of
daily rows, not the full history since Jan-2024, so each snapshot carries ~12-15 rows and their
union spans only 2026-07-02..2026-07-24 (~17 US business days). stage_a_screen requires >=30
usable observations AFTER a 20-period z-score burn-in, i.e. >=51 rows. The axis is therefore NOT
SCREENABLE at present. This is a data-coverage finding, not an economic verdict on the mechanism:
the hypothesis is UNTESTED, not rejected.

Stage A only -- ZERO promotion authority.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from libs.research.axis_screen import stage_a_screen  # noqa: E402

ETF = ROOT / "data" / "lake" / "bronze" / "etf_flows"
OUT = ROOT / "reports" / "axis_screens"
_NUM = re.compile(r"^\(?-?[\d,]+\.?\d*\)?$")


def _cell(x: str) -> float | None:
    x = x.replace("&nbsp;", " ").replace(",", "").strip()
    neg = x.startswith("(") and x.endswith(")")
    x = x.strip("()")
    try:
        v = float(x)
    except ValueError:
        return None
    return -v if neg else v


def _parse(path: Path) -> pd.Series:
    """Farside daily table -> Series of TOTAL net flow (US$m) indexed by UTC trading day."""
    html = path.read_text("utf-8", errors="replace")
    rows, out = re.findall(r"<tr.*?</tr>", html, re.S), {}
    for r in rows:
        cells = [re.sub(r"<[^>]+>", "", c).replace("&nbsp;", " ").strip()
                 for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", r, re.S)]
        if not cells:
            continue
        m = re.match(r"^(\d{2} \w{3} \d{4})$", cells[0].strip())
        if not m:
            continue
        vals = [_cell(c) for c in cells[1:] if _NUM.match(c.replace("&nbsp;", " ").strip())]
        if not vals:
            continue
        day = pd.Timestamp(datetime.strptime(m.group(1), "%d %b %Y"), tz="UTC")
        out[day] = vals[-1]                     # trailing column is the Total
    return pd.Series(out).sort_index()


def _btc() -> pd.Series:
    fs = sorted((ROOT / "data/lake/bronze/crypto/BTCUSDT/D1").glob("year=*/month=*/part-0.parquet"))
    df = pd.concat([pd.read_parquet(f) for f in fs])
    df["day"] = pd.to_datetime(df["timestamp"], utc=True).dt.floor("D")
    return df.sort_values("day").drop_duplicates("day").set_index("day")["close"]


def main() -> None:
    flows = pd.concat([_parse(p) for p in sorted(ETF.glob("*.html"))])
    flows = flows[~flows.index.duplicated(keep="last")].sort_index()

    px = _btc()
    d = pd.DataFrame({"flow": flows}).join(pd.DataFrame({"px": px}), how="inner")
    d["ret"] = d["px"].pct_change()
    d = d.dropna()

    need = 51
    trials = []
    if len(d) >= need:
        sig, ret = d["flow"].to_numpy(), d["ret"].to_numpy()
        trials.append(stage_a_screen(sig[:-1], ret[1:], name="etf_net_flow_T1lag->btc_1d"))
        trials.append(stage_a_screen(sig, ret, name="LOOKAHEAD-CONTROL_etf_flow_naive->btc_1d"))
    else:
        for nm in ("etf_net_flow_T1lag->btc_1d", "etf_net_flow_T1lag->btc_5d",
                   "etf_net_flow_T1lag->btc_20d", "LOOKAHEAD-CONTROL_etf_flow_naive->btc_1d"):
            trials.append({"name": nm, "verdict": "INSUFFICIENT-DATA", "n": len(d),
                           "required": need,
                           "reason": "Farside page serves only a trailing window per snapshot; "
                                     "2 snapshots union to ~17 US business days vs 51 required "
                                     "(30 obs + 20 z-burn-in)."})

    out = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "axis": "etf_flows",
        "n_days": len(d),
        "n_required": need,
        "range": [str(d.index.min().date()), str(d.index.max().date())] if len(d) else None,
        "flow_days_parsed": {str(k.date()): float(v) for k, v in flows.items()},
        "alignment": (
            "Farside net flow is per US TRADING day t "
            "(US business days only; crypto trades 7d/wk). "
            "Creations settle T+1 and the table for day t publishes the EVENING of t+1, so flow[t] "
            "is NOT knowable at the day-t crypto close nor at the day-t+1 open. The naive build "
            "flow[t]->ret[t+1] is therefore LOOK-AHEAD and is retained only as a labelled control. "
            "The correct build lags the flow one extra day so the harness's t->t+1 step lands on "
            "flow[t]->BTC ret[t+2], ~24h after publication."),
        "verdict": "NOT-SCREENABLE (insufficient history) -- hypothesis UNTESTED, not rejected",
        "next_step": (
            "Backfill full daily history since 2024-01-11 (ETF launch) from an archive source, or "
            "accrue daily snapshots. At 1 snapshot/day the union reaches the 51-row minimum in "
            "~34 more US business days. Do NOT screen before then -- a 17-row screen would be "
            "noise dressed as a verdict."),
        "trials": trials,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "etf_flows.json").write_text(json.dumps(out, indent=1, default=str), "utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "flow_days_parsed"},
                     indent=1, default=str))
    print(f"\nparsed flow days: {len(flows)}  joined to BTC: {len(d)}  required: {need}")


if __name__ == "__main__":
    main()
