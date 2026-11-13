"""CROWDING CONDITIONER: who is already on the trade, measured from CFTC positioning.

Trader-brain gap #9 (2026-11-13): crowding had been checked on 0 of 57,538 ideas and nothing
reached sizing. A human trader asks "who is already in this?" before sizing up; this organ
answers it per MT5 instrument from the CFTC's own free weekly reports and turns the answer into
a TWO-SIDED cell modifier, but only as far as the desk's own history shows the answer pays.

INPUTS (publicreporting.cftc.gov, Socrata, read through the fail-closed robots gate):
  legacy   non-commercial (large speculator) net share of open interest, every COT_MAP symbol
  tff      leveraged-funds net share of open interest (Traders in Financial Futures), FX only
Each series becomes a 3-year rolling z-score, sign-aligned so a positive z means the crowd is
LONG the MT5 instrument, lagged one full report week (a Tuesday snapshot is used from the
following Tuesday; the CFTC publishes on Friday, so the lag errs safe).

RETAIL SENTIMENT IS UNMEASURED, named and not guessed: the broker sentiment widgets that publish
retail long/short shares (IG, OANDA, Myfxbook) carry terms that are unclear or refuse automated
use, so no feed is read until one is confirmed. See `RETAIL`.

THE EVIDENCE TEST, before any modifier is proposed. For every instrument with D1 bars in the
lake, the forward 20-day return is sampled on a NON-OVERLAPPING grid. A contrarian bet is taken
when |z| >= EXTREME_Z: return x -sign(z). Pooled over instruments, its mean, t-stat and n decide:
  EVIDENCED   t >= T_MIN and n >= N_MIN: tilt k = clip(per-period Sharpe of the bet, 0, K_MAX)
  UNPROVEN    otherwise: k = 0, with the missed-growth line saying what is not being used
`modifier(symbol, direction)` returns 1 + k for a cell trading AGAINST a crowded side and 1 - k
for one trading WITH it (Growth governance: every capital modifier is two-sided), 1.0 when the
instrument is not crowded or the evidence is UNPROVEN.

ZERO SIZING AUTHORITY HERE. The artifact is an INPUT the gauntlet and the allocator may read;
nothing in this file sends, sizes or vetoes an order.

    python research/crowding_conditioner.py [--offline]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import cot_source as CS  # noqa: E402

OUT = DESK / "reports" / "CROWDING_CONDITIONER.json"
LAKE = ROOT / "data" / "lake"

TFF_BASE = "https://publicreporting.cftc.gov/resource/gpe5-46if.json"
#: Financial futures the TFF report covers, keyed like COT_MAP (same CFTC contract codes).
TFF_SYMBOLS = ("EURUSD", "GBPUSD", "AUDUSD", "USDJPY", "USDCHF", "USDCAD")
Z_WEEKS = 156
EXTREME_Z = 2.0
HORIZON_D = 20
T_MIN = 2.0
N_MIN = 30
K_MAX = 0.5
#: The CFTC publishes weekly; a daily rebuild catches Friday's report within a day of it.
REBUILD_H = 20
RETAIL = {"status": "UNMEASURED",
          "why": ("no retail-sentiment feed with confirmed terms for automated use; the broker "
                  "sentiment widgets (IG, OANDA, Myfxbook) are unclear or refuse it, and "
                  "unclear terms fail closed")}
MISSED_GROWTH = ("while UNPROVEN the modifier is 1.0 for every cell: a crowded instrument gets "
                 "no extra size against the crowd and no less with it, so any true "
                 "positioning-unwind premium goes unharvested")


def _net_tff(rows: list[dict[str, Any]]) -> pd.Series:
    df = pd.DataFrame(rows)
    need = {"report_date_as_yyyy_mm_dd", "lev_money_positions_long",
            "lev_money_positions_short", "open_interest_all"}
    if df.empty or not need <= set(df.columns):
        return pd.Series(dtype="float64")
    dt = pd.to_datetime(df["report_date_as_yyyy_mm_dd"], utc=True)
    oi = df["open_interest_all"].astype("float64").replace(0.0, float("nan"))
    net = (df["lev_money_positions_long"].astype("float64")
           - df["lev_money_positions_short"].astype("float64")) / oi
    return pd.Series(net.to_numpy(), index=dt).sort_index().dropna()


def fetch_tff(code: str) -> pd.Series:
    url = (f"{TFF_BASE}?$where=cftc_contract_market_code='{code}'"
           "&$select=report_date_as_yyyy_mm_dd,lev_money_positions_long,"
           "lev_money_positions_short,open_interest_all"
           "&$order=report_date_as_yyyy_mm_dd ASC&$limit=5000")
    return _net_tff(CS._get(url))


def zscore(net: pd.Series, sign: float, z_weeks: int = Z_WEEKS) -> pd.Series:
    """Rolling z, sign-aligned to the MT5 instrument, lagged one report week."""
    if len(net) < z_weeks // 2:
        return pd.Series(dtype="float64")
    roll = net.rolling(z_weeks, min_periods=52)
    return (sign * (net - roll.mean()) / roll.std()).shift(1).dropna()


def state_of(z: float | None) -> str:
    if z is None or not math.isfinite(z):
        return "UNMEASURED"
    if z >= EXTREME_Z:
        return "CROWDED_LONG"
    if z <= -EXTREME_Z:
        return "CROWDED_SHORT"
    return "NEUTRAL"


def evidence(z: dict[str, pd.Series], closes: pd.DataFrame,
             horizon: int = HORIZON_D) -> dict[str, Any]:
    """Pooled contrarian return at extremes on a non-overlapping forward grid."""
    bets: list[float] = []
    per: dict[str, int] = {}
    for sym, zs in z.items():
        if sym not in closes.columns or zs.empty:
            continue
        px = closes[sym].dropna()
        if len(px) <= horizon:
            continue
        zd = zs.reindex(zs.index.union(px.index)).sort_index().ffill().reindex(px.index)
        fwd = (px.shift(-horizon) / px - 1.0)
        grid = pd.DataFrame({"z": zd, "fwd": fwd}).iloc[::horizon].dropna()
        hit = grid[grid["z"].abs() >= EXTREME_Z]
        vals = (-hit["z"].apply(lambda v: 1.0 if v > 0 else -1.0) * hit["fwd"]).tolist()
        bets.extend(vals)
        per[sym] = len(vals)
    n = len(bets)
    if n < 2:
        return {"status": "UNPROVEN", "n": n, "per_symbol": per, "k": 0.0,
                "why": "fewer than two extreme readings with a forward return"}
    s = pd.Series(bets)
    mean, sd = float(s.mean()), float(s.std(ddof=1))
    t = mean / (sd / math.sqrt(n)) if sd > 0 else 0.0
    sharpe = mean / sd if sd > 0 else 0.0
    ok = t >= T_MIN and n >= N_MIN
    return {"status": "EVIDENCED" if ok else "UNPROVEN", "n": n, "mean": mean, "sd": sd,
            "t": round(t, 3), "per_period_sharpe": round(sharpe, 4), "per_symbol": per,
            "horizon_d": horizon, "extreme_z": EXTREME_Z,
            "k": round(min(K_MAX, max(0.0, sharpe)), 4) if ok else 0.0,
            "rule": f"EVIDENCED needs t >= {T_MIN} and n >= {N_MIN}; k = clip(Sharpe, 0, {K_MAX})"}


def modifier(symbol: str, direction: int, doc: dict[str, Any] | None = None) -> float:
    """Two-sided multiplier for a cell on `symbol` trading `direction` (+1 long, -1 short)."""
    if doc is None:
        try:
            doc = json.loads(OUT.read_text("utf-8"))
        except (OSError, ValueError):
            return 1.0
    k = float(((doc or {}).get("evidence") or {}).get("k") or 0.0)
    st = (((doc or {}).get("instruments") or {}).get(symbol) or {}).get("state")
    if k <= 0 or st not in ("CROWDED_LONG", "CROWDED_SHORT") or direction == 0:
        return 1.0
    crowd = 1 if st == "CROWDED_LONG" else -1
    return 1.0 - k if direction * crowd > 0 else 1.0 + k


def _load_closes() -> pd.DataFrame:
    try:
        from screen_cot_positioning import CLASSES, load_closes  # type: ignore[import-not-found]
        return load_closes(CLASSES, "2010-01-01", LAKE)
    except Exception:
        return pd.DataFrame()


def build(*, legacy: Callable[[str], pd.Series], tff: Callable[[str], pd.Series],
          refusal: Callable[[str], str | None], closes: pd.DataFrame,
          now: datetime) -> dict[str, Any]:
    gate = {"legacy": refusal(CS._BASE), "tff": refusal(TFF_BASE)}
    zs: dict[str, dict[str, pd.Series]] = {"legacy": {}, "tff": {}}
    inst: dict[str, Any] = {}
    for sym, (code, sign) in CS.COT_MAP.items():
        row: dict[str, Any] = {}
        for src, fetch in (("legacy", legacy), ("tff", tff)):
            if src == "tff" and sym not in TFF_SYMBOLS:
                continue
            if gate[src]:
                row[src] = {"state": "UNMEASURED", "why": f"ROBOTS_REFUSED: {gate[src]}"}
                continue
            try:
                z = zscore(fetch(code), sign)
            except Exception as exc:                     # one contract never breaks the rest
                row[src] = {"state": "UNMEASURED", "why": f"fetch failed ({type(exc).__name__})"}
                continue
            if z.empty:
                row[src] = {"state": "UNMEASURED", "why": "history shorter than 78 weeks"}
                continue
            zs[src][sym] = z
            last = float(z.iloc[-1])
            row[src] = {"z": round(last, 3), "state": state_of(last),
                        "as_of": z.index[-1].date().isoformat()}
        live = [r for r in row.values() if r.get("state") not in (None, "UNMEASURED")]
        # The instrument's state is the legacy (speculator) reading; TFF agreeing or
        # disagreeing rides along so a reader can see both crowds.
        row["state"] = (row.get("legacy") or {}).get("state") or (
            live[0]["state"] if live else "UNMEASURED")
        inst[sym] = row
    ev: dict[str, Any] = evidence(zs["legacy"], closes) if not closes.empty else {
        "status": "UNPROVEN", "n": 0, "k": 0.0, "why": "no lake D1 bars readable"}
    doc = {"generated_at": now.isoformat(timespec="seconds"),
           "source": "CFTC legacy COT + Traders in Financial Futures (publicreporting.cftc.gov)",
           "instruments": inst, "evidence": ev, "retail_sentiment": RETAIL,
           "modifier_rule": ("against a crowded side: 1 + k; with it: 1 - k; otherwise 1.0. "
                             "k is 0 unless the pooled contrarian test is EVIDENCED."),
           "authority": "input only: nothing here sizes, sends or vetoes an order"}
    if float(ev.get("k") or 0.0) <= 0:
        doc["missed_growth"] = MISSED_GROWTH
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--offline", action="store_true", help="no network: refuse both feeds")
    ap.add_argument("--force", action="store_true", help="rebuild even when fresh")
    a = ap.parse_args(argv)
    now = datetime.now(tz=UTC)
    try:
        prev = json.loads(OUT.read_text("utf-8"))
        age_h = (now - datetime.fromisoformat(prev["generated_at"])).total_seconds() / 3600
    except (OSError, ValueError, KeyError, TypeError):
        age_h = None
    if not a.force and age_h is not None and age_h < REBUILD_H:
        print(json.dumps({"fresh": True, "age_h": round(age_h, 2)}))
        return 0
    from libs.data.datahub_feeds import robots_refusal
    refuse: Callable[[str], str | None] = (
        (lambda _u: "offline run") if a.offline else robots_refusal)
    doc = build(legacy=CS.fetch_net_spec, tff=fetch_tff, refusal=refuse,
                closes=_load_closes(), now=now)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1) + "\n", "utf-8")
    os.replace(tmp, OUT)
    crowded = sorted(s for s, r in doc["instruments"].items()
                     if r["state"].startswith("CROWDED"))
    print(json.dumps({"evidence": {k: doc["evidence"].get(k) for k in ("status", "n", "t", "k")},
                      "crowded": crowded}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
