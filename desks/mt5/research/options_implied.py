"""OPTIONS AND IMPLIED VOL -- the lawful route to the vol-surface class the desk lacks, and the
PROXY family it can build today from data it owns.

    python desks/mt5/research/options_implied.py --once
    python desks/mt5/research/options_implied.py --once --dry-run   # compute, write nothing

WHY THIS EXISTS (data_class_gap #2, `options_implied_vol`, score 6.26 with nothing ingested). Every
macro/FX desk reads 25-delta risk reversals and the ATM vol term structure daily. The gap module
names this file as the class's producer. It does two things, and labels each for what it is.

1. THE IMPLIED SOURCES, ON THE ONE TERMS REGISTER. Every free publisher of option-implied measures
   for the MT5 universe was read on 2026-10-29 (libs/data/terms_fence.SOURCE_POLICY): the
   Minneapolis Fed's market-based probabilities (option-implied mean, sd, skew and tails for corn,
   soybeans, wheat, gold, crude, the euro, the yen and the S&P 500 -- the best fit by far) permit
   "research and informational purposes only" and name no automated access; Eurex bars copying
   without written permission; Cboe's and CME's terms are held routes already; JPX's terms page
   was unreadable. NONE permits live input, so every one is IDEAS_ONLY (or held) and this module
   fetches none of them. The Minneapolis Fed file's parser (`mpd_frame`) is built and tested on a
   fixture so the day a permitting clause is quoted into its row the door is one spec away; until
   then each source's missed-growth line is in the artifact, delta E[log W] UNMEASURED.

2. THE PROXY FAMILY, FROM THE BROKER'S OWN BARS. Realized volatility term structure and realized
   skew per hypothesis-lane symbol, from its MT5 H1 bars: rv over 5/21/63 days, the 5/63 and
   21/63 log term slopes, the 63-day skew of daily returns and the 21-day downside share of
   intraday variance (a realized stand-in for the risk reversal). THIS IS NOT IMPLIED VOL and is
   never called so: provider `MT5_PROXY`, every series name begins "PROXY realized". The series
   land in the world dataset hunter's store (`world_dataset_hunter.ingest_series`), mapped to the
   symbol whose bars made them, so `world_macro_proposer` mints `world_macro_state` cells on them
   -- the form the desk's cells already consume; no second lane. A day's value is knowable once
   its last bar closes: available at the next 00:00 UTC (H1 bars are UTC-indexed), never sooner.

Terms of the proxy: the desk's own broker bars; no third-party input.
Clock: `hourly_cycle:options_implied` (department `data`, layer `information`); a symbol is
recomputed once its dataset is older than `REFRESH_H`.
Artifact: desks/mt5/reports/OPTIONS_IMPLIED.json
"""
from __future__ import annotations

import argparse
import io
import json
import math
import re
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

REPORT = DESK / "reports" / "OPTIONS_IMPLIED.json"
BARS = DESK / "data" / "universe"
UNMEASURED = "UNMEASURED"
PROVIDER = "MT5_PROXY"
REFRESH_H = 20.0
#: The pass stops starting symbols after this many seconds (the leg's cap sits above it); the
#: freshness skip means the next pass resumes with the symbols this one did not reach.
DEFAULT_BUDGET_S = 240.0
#: Daily bars a symbol needs before its 63-day window says anything.
MIN_DAYS = 90
#: A UTC day counts only with this many H1 bars (a holiday stub is not a day of variance).
MIN_BARS_PER_DAY = 4
WINDOWS = (5, 21, 63)
ANNUAL = 252.0

#: The implied-vol sources read for this class, each a row key of terms_fence.SOURCE_POLICY (or
#: a host with no row: TERMS_UNMEASURED, never OK). What each would give the desk.
IMPLIED_SOURCES: tuple[tuple[str, str, str], ...] = (
    ("minneapolis_fed_mpd", "minneapolisfed.org",
     ("option-implied distributions for CORN, SOYBEAN, WHEAT, XAUUSD, XTIUSD, EURUSD, USDJPY, "
      "US500")),
    ("eurex_web", "eurex.com", "index-option settlements for GER40 and EU50"),
    ("cboe_delayed_index_values", "cboe.com", "VIX-family indices for US500 and NAS100"),
    ("cme_margin_changes", "cmegroup.com", "CME option bulletins (FX, metals, grains)"),
    ("", "jpx.co.jp", "Nikkei 225 option statistics for JP225 (terms page unreadable)"),
)


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(t: datetime) -> str:
    return t.isoformat(timespec="seconds")


# ---------------------------------------------------------------- IDEAS_ONLY parser (MPD) ----
_MPD_MEASURES = ("mu", "sd", "skew", "kurt", "p10", "p50", "p90", "prdec", "princ")


def mpd_frame(raw: bytes) -> Any:
    """Minneapolis Fed `mpd_stats.csv` -> a long frame [series_code, period, value]: one series
    per market x measure (mean, sd, skew, kurtosis, 10/50/90th percentiles, the probability of a
    large decrease / increase). IDEAS_ONLY (row `minneapolis_fed_mpd`): tested on fixtures and
    never fetched as live input by this module."""
    import pandas as pd

    text = raw.decode("utf-8-sig", "replace")
    if text.lstrip()[:1] == "<":
        raise ValueError("served_html")
    df = pd.read_csv(io.StringIO(text), low_memory=False)
    cols = {re.sub(r"[^a-z0-9]", "", str(c).lower()): c for c in df.columns}
    mcol = cols.get("market")
    dcol = next((cols[k] for k in ("idt", "date", "asof") if k in cols), None)
    if mcol is None or dcol is None:
        raise ValueError(f"mpd columns {sorted(cols)[:12]}")
    days = pd.to_datetime(df[dcol].astype(str), errors="coerce", format="mixed")
    frames = []
    for meas in _MPD_MEASURES:
        if meas not in cols:
            continue
        vals = pd.to_numeric(df[cols[meas]], errors="coerce")
        code = df[mcol].astype(str).str.strip().str.lower().str.replace(r"[^a-z0-9]+", "_",
                                                                        regex=True)
        frames.append(pd.DataFrame({"series_code": code + "_" + meas,
                                    "period": days.dt.strftime("%Y-%m-%d"), "value": vals}))
    if not frames:
        raise ValueError("mpd: no measure columns")
    out = pd.concat(frames, ignore_index=True).dropna(subset=["period", "value"])
    return out.drop_duplicates(["series_code", "period"], keep="last")


def implied_sources() -> list[dict[str, Any]]:
    """Each implied-vol source with its register row, live-input verdict and missed-growth line."""
    from libs.data import terms_fence as tf

    out = []
    for key, host, gives in IMPLIED_SOURCES:
        row = tf.SOURCE_POLICY.get(key) if key else None
        if row is None:
            out.append({"source": key or host, "host": host, "gives": gives,
                        "live_input": "TERMS_UNMEASURED",
                        "missed_growth": {"source": key or host, "kind": "terms_unmeasured",
                                          "delta_elogw": UNMEASURED,
                                          "cause": ("no SOURCE_POLICY row: the publisher's own "
                                                    "terms page was unreadable on 2026-10-29, so "
                                                    "the growth at stake is UNMEASURED")}})
            continue
        refused = bool(row.get("held_route")) or tf.live_input_status(key) in (
            tf.IDEAS_ONLY, tf.METHOD_BLOCKED)
        line = tf.held_missed_growth(key, live_input_refusal=not tf.held_on_terms(key))
        out.append({"source": key, "host": host, "gives": gives,
                    "status": tf.live_input_status(key), "terms_state": tf.terms_state(key),
                    "live_input": "REFUSED" if refused else "PERMITTED",
                    "parser": "mpd_frame" if key == "minneapolis_fed_mpd" else None,
                    "missed_growth": line if refused else None})
    return out


# -------------------------------------------------------------------- the PROXY family ----
def daily_returns(bars: Any) -> tuple[Any, Any]:
    """(daily close-to-close log returns, per-day intraday H1 log returns frame) on UTC days
    holding at least MIN_BARS_PER_DAY bars."""
    import numpy as np
    import pandas as pd

    close = bars["close"].astype("float64")
    close = close[np.isfinite(close) & (close > 0)]
    idx = close.index
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    close = pd.Series(close.to_numpy(), index=idx.tz_convert("UTC"))
    day = close.index.normalize()
    counts = close.groupby(day).size()
    good = counts[counts >= MIN_BARS_PER_DAY].index
    last = close.groupby(day).last().reindex(good)
    rd = np.log(last).diff().dropna()
    rh = np.log(close).diff()
    rh = rh[day.isin(good)].dropna()
    return rd, rh


def proxy_features(bars: Any) -> Any:
    """Per UTC day: rv_5d, rv_21d, rv_63d (annualised), the log term slopes rv5/rv63 and
    rv21/rv63, the 63-day skew of daily returns, the 21-day intraday rv and the 21-day downside
    share of intraday variance. Each value uses only days up to and including its own."""
    import numpy as np
    import pandas as pd

    rd, rh = daily_returns(bars)
    if len(rd) < MIN_DAYS:
        return pd.DataFrame()
    out = pd.DataFrame(index=rd.index)
    for n in WINDOWS:
        out[f"rv_{n}d"] = np.sqrt(ANNUAL * (rd ** 2).rolling(n, min_periods=n).mean())
    with np.errstate(divide="ignore", invalid="ignore"):
        out["rv_term_5_63"] = np.log(out["rv_5d"] / out["rv_63d"])
        out["rv_term_21_63"] = np.log(out["rv_21d"] / out["rv_63d"])
    out["rskew_63d"] = rd.rolling(63, min_periods=63).skew()
    day = rh.index.normalize()
    sq = (rh ** 2).groupby(day).sum().reindex(out.index).fillna(0.0)
    dn = ((rh.clip(upper=0.0)) ** 2).groupby(day).sum().reindex(out.index).fillna(0.0)
    tot21 = sq.rolling(21, min_periods=21).sum()
    out["rv_intraday_21d"] = np.sqrt(ANNUAL * tot21 / 21.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        out["downside_share_21d"] = dn.rolling(21, min_periods=21).sum() / tot21
    return out.replace([np.inf, -np.inf], np.nan)


def proxy_series(sym: str, feats: Any) -> list[dict[str, Any]]:
    """Feature frame -> the hunter's series dicts, every name labelled PROXY realized."""
    out = []
    for col in feats.columns:
        s = feats[col].dropna()
        if s.empty:
            continue
        pts = [(d.strftime("%Y-%m-%d"), float(v)) for d, v in s.items()
               if math.isfinite(float(v))]
        out.append({"code": col, "freq": "daily", "dims": {}, "stems": [sym],
                    "name": (f"PROXY realized {col} of {sym} from MT5 broker bars (realized, "
                             "not implied vol)"),
                    "points": pts})
    return out


def _load_bars(sym: str, base: Path = BARS) -> Any:
    import pandas as pd

    p = base / f"{sym}_H1.parquet"
    if not p.exists():
        return None
    try:
        df = pd.read_parquet(p)
    except Exception:
        return None
    if "close" not in df.columns or not isinstance(df.index, pd.DatetimeIndex):
        return None
    return df.sort_index()


def _fresh(sym: str, now: datetime, wdh: Any) -> bool:
    meta = wdh._read_json(wdh.meta_path(PROVIDER, f"RVOL_{sym}"), {}) or {}
    at = wdh._parse_iso(meta.get("updated_at"))
    return bool(at and (now - at).total_seconds() < REFRESH_H * 3600)


def run(*, now: datetime | None = None, dry_run: bool = False, bars: Path = BARS,
        symbols: list[str] | None = None, budget_s: float = DEFAULT_BUDGET_S
        ) -> dict[str, Any]:
    from research import world_dataset_hunter as wdh

    now = now or _now()
    t0 = time.monotonic()
    uni = [s for s, _, _ in wdh.hypothesis_universe()] if symbols is None else list(symbols)
    stats: Counter[str] = Counter()
    qstats: Counter[str] = Counter()
    per: dict[str, Any] = {}
    for sym in uni:
        if time.monotonic() - t0 > budget_s:
            stats["deferred_budget"] += 1
            continue
        if not dry_run and _fresh(sym, now, wdh):
            stats["fresh_skipped"] += 1
            continue
        df = _load_bars(sym, bars)
        if df is None:
            stats["no_h1_bars"] += 1
            continue
        feats = proxy_features(df)
        if feats.empty:
            stats["too_short"] += 1
            per[sym] = {"status": "too_short", "min_days": MIN_DAYS}
            continue
        series = proxy_series(sym, feats)
        last = feats.dropna(how="all").index.max()
        row: dict[str, Any] = {"series": len(series), "last_day": str(last.date()),
                               "latest": {c: (round(float(v), 6) if v == v else None)
                                          for c, v in feats.loc[last].items()}}
        if not dry_run:
            res = wdh.ingest_series(PROVIDER, f"RVOL_{sym}",
                                    f"PROXY realized vol term structure and skew {sym}", series,
                                    now=now, base_score=wdh.dataset_score(PROVIDER, "volatility"),
                                    declared_lag=1, qstats=qstats)
            row.update({"rows_added": res["rows_added"], "passed": res["passed"]})
            stats["rows_appended"] += int(res["rows_added"])
        stats["symbols_computed"] += 1
        per[sym] = row
    measured = bool(uni)
    return {
        "generated_at": _iso(now),
        "organ": "desks/mt5/research/options_implied.py",
        "leg": "hourly_cycle:options_implied",
        "dry_run": dry_run,
        "label": ("PROXY: realized volatility term structure and realized skew from MT5 broker "
                  "bars -- NOT implied volatility"),
        "proxy": {
            "provider": PROVIDER, "store": "desks/mt5/data/world_datasets/obs/mt5_proxy/",
            "symbols_in_lane": len(uni) if measured else UNMEASURED,
            "symbols_computed": stats["symbols_computed"],
            "fresh_skipped": stats["fresh_skipped"], "no_h1_bars": stats["no_h1_bars"],
            "too_short": stats["too_short"], "deferred_budget": stats["deferred_budget"],
            "rows_appended": stats["rows_appended"] if not dry_run else UNMEASURED,
            "quality_by_reason": dict(qstats),
            "available": "next 00:00 UTC after the day's last bar (declared_lag 1 day)",
            "per_symbol": per},
        "implied_sources": implied_sources(),
        "rule": ("no implied-vol source is fetched as live input until its own terms quote a "
                 "permitting clause into its SOURCE_POLICY row; the proxy is labelled PROXY and "
                 "never called implied vol; absence is UNMEASURED, never 0"),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--once", action="store_true", help="one pass (the default)")
    ap.add_argument("--budget-s", type=float, default=DEFAULT_BUDGET_S)
    ap.add_argument("--dry-run", action="store_true",
                    help="compute the proxy and read the register; write only the report")
    args = ap.parse_args(argv)
    rep = run(dry_run=args.dry_run, budget_s=args.budget_s)
    from research.world_dataset_hunter import write_json
    write_json(REPORT, json.loads(json.dumps(rep, default=str)))
    p = rep["proxy"]
    refused = sum(1 for s in rep["implied_sources"] if s["live_input"] != "PERMITTED")
    print(f"options_implied: proxy symbols={p['symbols_computed']} rows={p['rows_appended']} "
          f"fresh={p['fresh_skipped']} no_bars={p['no_h1_bars']} short={p['too_short']}; "
          f"implied sources {len(rep['implied_sources'])}, not live {refused}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
