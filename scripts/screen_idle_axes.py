"""Convert the three IDLE ingested axes (max_audit `data-utilization-paralysis`) MECHANISM-FIRST.

Idle axes reported by ``research_memory.py coverage``: ``crypto`` (bronze research lake),
``try_premium`` (Turkey/lira), ``onchain_activity`` (Bitcoin settlement throughput). Each gets
exactly ONE economically-motivated hypothesis, screened through the audited
``libs.research.axis_screen.stage_a_screen`` harness (angle-20 de-contamination gate baked in),
across a pre-declared construction x horizon grid. EVERY cell is a DSR-counted trial and every
cell is written to ``data/idle_axis_screen.json`` -- including the ones that fail. Reporting only
the survivors would be garden-of-forking-paths p-hacking.

ZERO PROMOTION AUTHORITY (two-stage law). A pass earns a pre-registered forward clock, never a cent.

--------------------------------------------------------------------------------------------------
SAMPLING CONVENTION (declared once, applies to every cell)
--------------------------------------------------------------------------------------------------
``stage_a_screen`` predicts ``target_ret[t+1]`` from ``z(signal[t])`` and uses ``target_ret[t]`` as
the SAME-PERIOD return for its de-contamination gate. Those two roles are only mutually consistent
when the sampling step equals the return horizon, so multi-day horizons are screened on
NON-OVERLAPPING h-day blocks: sample dates every ``h`` days, ``ret_h[k] = C[d_k]/C[d_{k-1}] - 1``,
``signal[k]`` observed at ``d_k``. Then ``fwd[k] = ret_h[k+1]`` is exactly the forward h-day return
after the signal, and ``tv[k] = ret_h[k]`` is exactly the h-day period the signal was observed in.
Passing daily-sampled OVERLAPPING h-day returns instead would put h-1 FUTURE days inside the
de-contamination variable and mechanically destroy any genuinely slow signal.

Consequence, declared: with block sampling the observations are already independent, so the
harness's TIME-axis deflator over-corrects for overlap by a factor h at h>1. That is the SAFE
direction (it can only turn a "refuted" into a "could not tell"), and each cell also records
``mdi_block`` = the honest 1.96/sqrt(n_blocks_eff) for the block design.

The CROSS-SECTIONAL factor is no longer assumed (L1.62). ``n_eff = n/(horizon_days * K/xs_neff)``
where ``xs_neff`` is this panel's MEASURED independent bets per bar, from
``libs.research.panel_breadth``. Dividing by the full K -- the behaviour here until 2026-08-13 --
asserts that K symbols carry ONE independent observation per bar, which on a cross-sectionally
demeaned target is wrong by roughly the panel width. An UNMEASURABLE panel keeps the full-K
divisor: absence resolves to the tighter reading, never to a clean one.

z-window is scaled so the lookback is a comparable calendar length at every horizon:
h=1 -> zwin 20 (20d), h=5 -> zwin 12 (60d), h=20 -> zwin 6 (120d).
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from libs.alpha_factory.hypothesis_novelty import PriorIdea, hypothesis_novelty
from libs.research.axis_screen import stage_a_screen
from libs.research.panel_breadth import measure_panel_breadth

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/idle_axis_screen.json"
ZWIN = {1: 20, 5: 12, 20: 6}
HORIZONS = (1, 5, 20)
TRIALS: list[dict] = []


# ----------------------------------------------------------------------------- novelty gate ----
def _graveyard_priors() -> list[PriorIdea]:
    """Every graveyard table row + the live sleeve roster, as priors for the novelty gate."""
    priors: list[PriorIdea] = []
    txt = (ROOT / "docs/graveyard.md").read_text("utf-8")
    for line in txt.splitlines():
        if not line.startswith("|") or line.startswith("|---") or "Hypothesis |" in line:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3:
            continue
        name, verdict, tag = cells[0], cells[1], cells[2]
        lesson = cells[3] if len(cells) > 3 else ""
        priors.append(PriorIdea(id=name[:60], category=tag,
                                statement=f"{name} {verdict} {lesson}"[:1500], lesson=lesson[:300]))
    # live sleeves that already trade these fields -- redundancy against a LIVE book is as
    # expensive as redundancy against the graveyard
    for sid, stmt, feats in [
        ("sleeve:taker_flow", "cross-sectional taker order-flow momentum: long perps with the "
         "strongest recent net taker buying, dollar-neutral perp book",
         ("taker_buy_frac", "xsec", "momentum", "perp")),
        ("sleeve:basis_carry", "perp-spot basis carry: long backwardated perps short rich premium",
         ("basis", "xsec", "carry", "perp")),
        ("sleeve:funding_carry", "cross-sectional perp funding carry book",
         ("funding", "xsec", "carry", "perp")),
        ("collector:onchain_activity_throughput",
         "bitcoin estimated USD on-chain economic throughput 20d z-score predicts next-day BTC "
         "return, reversal direction, daily horizon",
         ("onchain_throughput_usd", "daily_horizon", "btc_timing", "level_z20")),
    ]:
        priors.append(PriorIdea(id=sid, statement=stmt, features=feats, category="live"))
    return priors


def novelty(name: str, statement: str, features: tuple[str, ...]) -> dict:
    priors = _graveyard_priors()
    r = hypothesis_novelty(statement, features=features, priors=priors)
    out = {"candidate": name, "novelty_score": round(r.novelty_score, 3),
           "nearest_id": r.nearest_id, "nearest_similarity": round(r.nearest_similarity, 3),
           "is_redundant": r.is_redundant, "nearest_lesson": (r.nearest_lesson or "")[:200],
           "n_priors": len(priors)}
    print(f"NOVELTY {name}: score {out['novelty_score']} nearest={out['nearest_id']} "
          f"sim={out['nearest_similarity']} redundant={out['is_redundant']}")
    return out


# --------------------------------------------------------------------------------- helpers ----
def cell(axis: str, construction: str, signal: np.ndarray, ret: np.ndarray, h: int,
         *, target_kind: str, panel_width: int = 1, xs_neff: float | None = None,
         extra: dict | None = None) -> dict:
    """One DSR-counted trial: run the audited harness and record it whatever the verdict.

    `xs_neff` is the MEASURED cross-sectional breadth of the panel these flat arrays were stacked
    from (L1.62). Omitting it keeps the conservative full-`panel_width` divisor -- which asserts
    that K symbols carry ONE independent observation per bar, an assumption that ran unmeasured on
    this desk in both directions until 2026-08-13.
    """
    r = stage_a_screen(signal, ret, name=f"{axis}::{construction}::h{h}d",
                       zwin=ZWIN[h], horizon_days=float(h), panel_width=panel_width,
                       xs_neff=xs_neff)
    n_blocks = len(signal) / max(panel_width, 1)
    r.update({"axis": axis, "construction": construction, "horizon_days_target": h,
              "target_kind": target_kind, "zwin": ZWIN[h],
              "n_blocks_per_unit": round(n_blocks, 1),
              "mdi_block": round(float(
                  1.96 / np.sqrt(max(len(signal) / max(panel_width, 1), 1.0))), 4)})
    if extra:
        r.update(extra)
    TRIALS.append(r)
    print(f"  {construction:38s} h={h:2d}d n={r.get('n'):6d} IC={r.get('ic')} "
          f"same={r.get('same_period_corr')} resid={r.get('residual_ic')} "
          f"momSh={r.get('sharpe_momentum')} revSh={r.get('sharpe_reversal')} "
          f"pw={r.get('powered')} -> {r['verdict']}")
    return r


def block_idx(n: int, h: int) -> np.ndarray:
    """Right-aligned non-overlapping sample points so the LAST observation is always included."""
    return np.arange(n - 1, -1, -h)[::-1]


def http_json(url: str) -> dict | list:
    req = urllib.request.Request(url, headers={"User-Agent": "quant-idle-axis-screen"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


# ============================================================== AXIS 1: crypto (bronze lake) ====
CRYPTO_MECHANISM = (
    "Aggressive taker buying is liquidity DEMAND paid at the offer; when a perp absorbs heavy "
    "aggressive buying WITHOUT the price response that flow should have produced, the other side "
    "is a large passive seller distributing inventory, so cross-sectionally those perps should "
    "UNDERPERFORM their peers over the following days.")


def load_crypto_panel(min_bars: int = 600, top_n: int = 80) -> dict:
    root = ROOT / "data/lake/bronze/crypto"
    closes, tbfs, dvol = {}, {}, {}
    n_sym, n_short, n_no_tbf = 0, 0, 0
    t0 = time.time()
    for sym in sorted(os.listdir(root)):
        fs = glob.glob(f"{root}/{sym}/D1/**/*.parquet", recursive=True)
        if not fs:
            continue
        n_sym += 1
        df = (pd.concat([pd.read_parquet(f) for f in fs])
              .sort_values("timestamp").drop_duplicates("timestamp"))
        if len(df) < min_bars:
            n_short += 1
            continue
        if "taker_buy_frac" not in df.columns or df["taker_buy_frac"].notna().sum() < min_bars:
            n_no_tbf += 1          # 117/268 lake symbols carry no taker-flow column at all
            continue
        df = df.set_index(pd.DatetimeIndex(df["timestamp"]).tz_convert("UTC").normalize())
        closes[sym] = df["close"]
        tbfs[sym] = df["taker_buy_frac"]
        dvol[sym] = float((df["close"] * df["volume"]).median())
    print(f"  lake: {n_sym} symbols with D1; {n_short} dropped <{min_bars} bars; "
          f"{n_no_tbf} dropped no taker_buy_frac column; {len(dvol)} eligible")
    keep = sorted(dvol, key=lambda s: -dvol[s])[:top_n]
    close = pd.DataFrame({s: closes[s] for s in keep}).sort_index()
    tbf = pd.DataFrame({s: tbfs[s] for s in keep}).sort_index()
    ends = {s: close[s].last_valid_index() for s in keep}
    still_alive = sum(1 for s in keep if ends[s] is not None
                      and ends[s] >= close.index.max() - pd.Timedelta(days=5))
    print(f"  panel: {len(keep)}/{len(dvol)} symbols (>= {min_bars} bars, top {top_n} by median "
          f"$vol) {close.index.min().date()} -> {close.index.max().date()} "
          f"load {time.time() - t0:.0f}s | alive-at-end {still_alive}/{len(keep)} "
          f"(survivorship: "
          f"{'ALL alive -> lake is survivor-only' if still_alive == len(keep) else 'mixed'})")
    return {"close": close, "tbf": tbf, "symbols": keep, "still_alive": still_alive}


def screen_crypto(panel: dict) -> None:
    close, tbf, syms = panel["close"], panel["tbf"], panel["symbols"]
    dates = close.index
    for h in HORIZONS:
        idx = block_idx(len(dates), h)
        c_h = close.iloc[idx]
        ret_h = c_h.pct_change()
        # block-average aggressive-buy share over the h days ending at each sample date
        tbf_h = tbf.rolling(h, min_periods=max(1, h // 2)).mean().iloc[idx]
        # cross-sectional demeaning: relative return is the mechanism-appropriate target for an
        # asset-selection signal (rule: no reflexive absolute next-day BTC)
        rel_ret = ret_h.sub(ret_h.mean(axis=1), axis=0)
        c1 = tbf_h.sub(tbf_h.mean(axis=1), axis=0)                      # raw xsec flow deviation
        # C2: per-date cross-sectional OLS residual of flow on the SAME-period return -> the part
        # of aggressive buying that the price move does NOT explain ("absorbed" flow)
        c2 = pd.DataFrame(np.nan, index=c1.index, columns=c1.columns)
        for d in c1.index:
            x, y = ret_h.loc[d], c1.loc[d]
            m = x.notna() & y.notna()
            if m.sum() >= 10 and x[m].std() > 0:
                b = np.polyfit(x[m].to_numpy(), y[m].to_numpy(), 1)
                c2.loc[d, m[m].index] = y[m].to_numpy() - (b[0] * x[m].to_numpy() + b[1])
        for cname, sig in (("C1_raw_xsec_taker_buy_share", c1),
                           ("C2_return_residualised_taker_buy", c2)):
            S, R, used, kept = [], [], 0, []
            for s in syms:
                a, b = sig[s].to_numpy(), rel_ret[s].to_numpy()
                ok = ~(np.isnan(a) | np.isnan(b))
                # longest contiguous valid run for this symbol (delisted names simply end early)
                if ok.sum() < ZWIN[h] + 32:
                    continue
                i0, i1 = int(np.argmax(ok)), len(ok) - int(np.argmax(ok[::-1]))
                seg = slice(i0, i1)
                if np.isnan(a[seg]).any() or np.isnan(b[seg]).any():
                    aa, bb = a[seg], b[seg]
                    good = ~(np.isnan(aa) | np.isnan(bb))
                    aa, bb = aa[good], bb[good]
                else:
                    aa, bb = a[seg], b[seg]
                if len(aa) < ZWIN[h] + 32:
                    continue
                S.append(aa)
                R.append(bb)
                used += 1
                kept.append(s)
            sig_f, ret_f = np.concatenate(S), np.concatenate(R)
            # L1.62: measure this panel's cross-sectional breadth on the SAME symbols that were
            # stacked, from the date-aligned frames the stacking flattened. `panel_width=used`
            # alone asserts these `used` names carry ONE independent observation per bar; the
            # target here is the cross-sectionally DEMEANED return, whose product terms are very
            # nearly independent across names, so that assumption inflates the detection floor by
            # roughly sqrt(breadth). UNMEASURABLE keeps the conservative full-K divisor.
            b = measure_panel_breadth(sig[kept].to_numpy(), rel_ret[kept].to_numpy(),
                                      min_obs=ZWIN[h] + 32)
            cell("crypto", cname, sig_f, ret_f, h,
                 target_kind="cross-sectional RELATIVE return (xsec-demeaned)",
                 panel_width=used, xs_neff=b.xs_neff if b.measured else None,
                 extra={"symbols_stacked": used, "breadth": b.as_dict(),
                        "stack_boundary_z_rows": ZWIN[h] * (used - 1),
                        "stack_boundary_fwd_rows": used - 1,
                        "stack_boundary_frac": round(ZWIN[h] * (used - 1) / max(len(sig_f), 1), 4)})


# ================================================== AXIS 2: onchain_activity (BTC throughput) ===
ONCHAIN_MECHANISM = (
    "Bitcoin's on-chain settlement throughput is real blockspace demand that cannot be "
    "manufactured with leverage; adoption-driven demand for a supply-inelastic asset is absorbed "
    "over WEEKS, so throughput should lead BTC returns at a multi-week horizon -- the horizon at "
    "which the mechanism actually operates, and the one the desk's `no_edge_daily` kills never "
    "tested.")


def coinmetrics_btc() -> pd.Series:
    """Coin Metrics community daily BTC reference close -- the desk's DEEPEST clean price history.

    Alignment (declared, and VERIFIED against the lake before use): Coin Metrics ``PriceUSD`` dated
    d is the fixed close as of 00:00 UTC on d+1, i.e. the same instant as the Binance D1 bar
    labelled d. Empirical check on the 2515 overlapping days: same-date log-return corr +0.994,
    while shifting either series by one day collapses it to -0.047 / -0.066. Same day label = same
    instant; no look-ahead channel from the price leg.
    """
    out: dict = {}
    with (ROOT / "data/coinmetrics_flows.jsonl").open(encoding="utf-8") as fh:
        for ln in fh:
            ln = ln.strip()
            if not ln:
                continue
            try:
                r = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if r.get("asset") == "btc" and r.get("price_usd") and r.get("date"):
                out[pd.Timestamp(str(r["date"])[:10], tz="UTC")] = float(r["price_usd"])
    return pd.Series(out).sort_index()


def screen_onchain(btc: pd.Series, deep: pd.Series | None = None) -> None:
    series = {}
    for chart, tag in (("estimated-transaction-volume-usd", "A_usd_denominated"),
                       ("estimated-transaction-volume", "B_btc_denominated_price_free")):
        d = http_json(f"https://api.blockchain.info/charts/{chart}"
                      f"?timespan=all&format=json&sampled=false")
        vals = d.get("values", []) if isinstance(d, dict) else []
        series[tag] = pd.Series(
            {pd.Timestamp(datetime.fromtimestamp(int(p["x"]), tz=UTC).date(), tz="UTC"):
             float(p["y"]) for p in vals}).sort_index()
        print(f"  {tag}: n={len(series[tag])} {series[tag].index.min().date()} -> "
              f"{series[tag].index.max().date()} unit={d.get('unit')}")

    # price legs: the lake (2019-09 ->, matches every other axis) and, if supplied, the deep
    # Coin Metrics history (2010-07 ->). PRE-DECLARED, before any IC is computed: the deep leg is
    # run at h=1d ONLY. n_blocks there is ~5.8k, so 1.96/sqrt(n_blocks)=0.026 finally sits UNDER
    # the harness's ic_min=0.03 and a null becomes a real refutation instead of "could not tell";
    # at h=5 (1.15k blocks -> 0.058) and h=20 (288 -> 0.116) the deeper sample is still blind, so
    # those cells could not change any verdict and are not run. This is a power calculation from
    # sample length alone -- it does not look at the data.
    legs = [("lake_btcusdt_2019", btc, HORIZONS)]
    if deep is not None:
        legs.append(("deep_coinmetrics_2010", deep, (1,)))
    for leg, px, horizons in legs:
        for tag, s in series.items():
            common = s.index.intersection(px.index)
            sv, bv = s.reindex(common).to_numpy(), px.reindex(common).to_numpy()
            print(f"  aligned {tag} [{leg}]: {len(common)} days "
                  f"{common.min().date()} -> {common.max().date()}")
            for h in horizons:
                idx = block_idx(len(common), h)
                b_h = bv[idx]
                ret_h = np.zeros(len(idx))
                ret_h[1:] = b_h[1:] / b_h[:-1] - 1.0
                sig_h = sv[idx]
                name = tag if leg == "lake_btcusdt_2019" else f"{tag}@{leg}"
                cell("onchain_activity", name, sig_h, ret_h, h,
                     target_kind="absolute BTC timing return (network-wide aggregate -> timing)",
                     extra={"aligned_days": len(common), "price_leg": leg,
                            "span": f"{common.min().date()}..{common.max().date()}"})


# ======================================================= AXIS 3: try_premium (lira debasement) ==
TRY_MECHANISM = (
    "Turkish savers facing chronic lira debasement and capital controls pay a RENT to hold "
    "dollar-denominated stablecoins; that rent -- USDT/TRY over the official USD/TRY -- is the "
    "direct price of local capital flight and, unlike the graveyarded BTC-venue premium (which "
    "differenced two BTC prices measured at different instants and died with same-day "
    "contamination -0.495), carries NO BTC price on either leg, so it cannot be mechanically "
    "contaminated by the same-day BTC return.")


def binance_daily_all(sym: str) -> pd.Series:
    out: dict = {}
    start = 0
    while True:
        rows = http_json(f"https://api.binance.com/api/v3/klines?symbol={sym}&interval=1d"
                         f"&limit=1000&startTime={start}")
        if not isinstance(rows, list) or not rows:
            break
        for r in rows:
            d = pd.Timestamp(datetime.fromtimestamp(int(r[0]) / 1000, tz=UTC).date(), tz="UTC")
            out[d] = float(r[4])
        if len(rows) < 1000:
            break
        start = int(rows[-1][0]) + 86_400_000
        time.sleep(0.2)
    return pd.Series(out).sort_index()


def yahoo_fx(sym: str) -> pd.Series:
    r = http_json(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
                  f"?interval=1d&range=10y")
    res = r["chart"]["result"][0]
    q = res["indicators"]["quote"][0]["close"]
    out = {}
    for t, c in zip(res["timestamp"], q, strict=False):
        if c is None:
            continue
        dt = datetime.fromtimestamp(int(t), tz=UTC)
        # Yahoo stamps the FX daily bar at LONDON midnight: 23:00Z during BST, 00:00Z during GMT.
        # Round to the London calendar day the bar actually belongs to, otherwise every summer bar
        # is mislabelled one day EARLY (the incumbent batch_premium._yahoo does exactly that).
        d = (dt + timedelta(hours=1)).date() if dt.hour >= 12 else dt.date()
        out[pd.Timestamp(d, tz="UTC")] = float(c)
    return pd.Series(out).sort_index()


def fx_lake_usdtry() -> pd.Series:
    def _load(sym: str) -> pd.Series:
        fs = glob.glob(f"{ROOT}/data/lake/bronze/fx/{sym}/D1/**/*.parquet", recursive=True)
        df = (pd.concat([pd.read_parquet(f) for f in fs])
              .sort_values("timestamp").drop_duplicates("timestamp"))
        return pd.Series(df["close"].to_numpy(),
                         index=pd.DatetimeIndex(df["timestamp"]).tz_convert("UTC").normalize())
    eurtry, eurusd = _load("EURTRY"), _load("EURUSD")
    common = eurtry.index.intersection(eurusd.index)
    return (eurtry.reindex(common) / eurusd.reindex(common)).sort_index()


def screen_try(btc: pd.Series) -> None:
    usdttry = binance_daily_all("USDTTRY")
    btctry = binance_daily_all("BTCTRY")
    btcusdt = binance_daily_all("BTCUSDT")
    fx_y = yahoo_fx("TRY=X")
    fx_l = fx_lake_usdtry()
    print(f"  USDTTRY n={len(usdttry)} {usdttry.index.min().date()}->{usdttry.index.max().date()}")
    print(f"  BTCTRY  n={len(btctry)}  {btctry.index.min().date()}->{btctry.index.max().date()}")
    print(f"  TRY=X   n={len(fx_y)}    {fx_y.index.min().date()}->{fx_y.index.max().date()}")
    print(f"  fxlake  n={len(fx_l)}    {fx_l.index.min().date()}->{fx_l.index.max().date()}")

    builds = {
        "T1_usdt_try_premium_vs_yahoo_fx": (usdttry / fx_y - 1.0),
        "T2_usdt_try_premium_vs_fxlake_eurcross": (usdttry / fx_l - 1.0),
        # FX-FREE falsifier: pure intra-venue triangular, all three legs the SAME Binance UTC close
        "T3_intravenue_triangular_fx_free": (btctry / (btcusdt * usdttry) - 1.0),
    }
    for tag, prem in builds.items():
        prem = prem.dropna()
        common = prem.index.intersection(btc.index)
        pv, bv = prem.reindex(common).to_numpy(), btc.reindex(common).to_numpy()
        std_pct = round(float(np.nanstd(pv) * 100), 4)
        print(f"  {tag}: aligned {len(common)}d {common.min().date()}->{common.max().date()} "
              f"premium std {std_pct}%")
        for h in HORIZONS:
            idx = block_idx(len(common), h)
            b_h = bv[idx]
            ret_h = np.zeros(len(idx))
            ret_h[1:] = b_h[1:] / b_h[:-1] - 1.0
            cell("try_premium", tag, pv[idx], ret_h, h,
                 target_kind="absolute BTCUSDT timing return (country-level capital-flight flow)",
                 extra={"aligned_days": len(common), "premium_std_pct": std_pct,
                        "span": f"{common.min().date()}..{common.max().date()}"})


# ------------------------------------------------------------------------------------- main ----
ALL_AXES = ("crypto", "onchain_activity", "try_premium")


def main(axes: tuple[str, ...] = ALL_AXES) -> None:
    """Screen the selected idle axes.

    ``axes`` exists so a run can SKIP an axis that must not be re-tested (``try_premium`` is
    graveyarded as ``try_premium_timing`` / ``timing_artifact``; the graveyard is permanent and
    re-testing an identical hypothesis is forbidden). Skipping is not deleting: trials for
    unselected axes are carried forward verbatim from the previous ``idle_axis_screen.json`` so a
    scoped re-run can never silently drop a recorded negative.
    """
    print("=" * 96)
    print("NOVELTY GATE (before compute) -- graveyard + live-sleeve priors")
    print("=" * 96)
    nov = []
    if "crypto" in axes:
        nov.append(novelty("crypto::taker_flow_absorption", CRYPTO_MECHANISM,
                           ("taker_buy_frac_residualised", "price_response", "absorption",
                            "xsec_relative_return", "perp")))
    if "onchain_activity" in axes:
        nov.append(novelty("onchain_activity::throughput_multiweek", ONCHAIN_MECHANISM,
                           ("onchain_throughput_btc_native", "multiweek_horizon", "btc_timing",
                            "supply_inelastic_absorption")))
    if "try_premium" in axes:
        nov.append(novelty("try_premium::stablecoin_rent", TRY_MECHANISM,
                           ("usdt_try_stablecoin_premium", "capital_flight", "no_btc_leg",
                            "btc_timing")))

    btc_fs = glob.glob(f"{ROOT}/data/lake/bronze/crypto/BTCUSDT/D1/**/*.parquet", recursive=True)
    btcdf = (pd.concat([pd.read_parquet(f) for f in btc_fs])
             .sort_values("timestamp").drop_duplicates("timestamp"))
    btc = pd.Series(btcdf["close"].to_numpy(),
                    index=pd.DatetimeIndex(btcdf["timestamp"]).tz_convert("UTC").normalize())
    print(f"\nBTCUSDT D1 (lake, Binance UTC-day close): n={len(btc)} "
          f"{btc.index.min().date()} -> {btc.index.max().date()}")

    if "crypto" in axes:
        print("\n" + "=" * 96)
        print("AXIS crypto  --", CRYPTO_MECHANISM)
        print("=" * 96)
        panel = load_crypto_panel()
        screen_crypto(panel)

    if "onchain_activity" in axes:
        print("\n" + "=" * 96)
        print("AXIS onchain_activity  --", ONCHAIN_MECHANISM)
        print("=" * 96)
        deep = coinmetrics_btc()
        print(f"  deep price leg (coinmetrics BTC close): n={len(deep)} "
              f"{deep.index.min().date()} -> {deep.index.max().date()}")
        screen_onchain(btc, deep=deep)

    if "try_premium" in axes:
        print("\n" + "=" * 96)
        print("AXIS try_premium  --", TRY_MECHANISM)
        print("=" * 96)
        screen_try(btc)

    # carry forward every recorded trial for axes NOT re-run this pass -- a scoped run must never
    # erase a negative someone else already paid for
    carried, carried_nov = [], []
    if OUT.exists():
        prev = json.loads(OUT.read_text("utf-8"))
        carried = [t for t in prev.get("trials", []) if t.get("axis") not in axes]
        carried_nov = [n for n in prev.get("novelty_gate", [])
                       if str(n.get("candidate", "")).split("::")[0] not in axes]
        for t in carried:
            t.setdefault("carried_from", prev.get("updated"))

    payload = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "stage": "A (zero promotion authority) -- a pass earns a forward clock, never capital",
        "defect": "data-utilization-paralysis (max_audit)",
        "mechanisms": {"crypto": CRYPTO_MECHANISM, "onchain_activity": ONCHAIN_MECHANISM,
                       "try_premium": TRY_MECHANISM},
        "axes_run_this_pass": list(axes),
        "novelty_gate": nov + carried_nov,
        "sampling_convention": __doc__.split("SAMPLING CONVENTION")[1].strip(),
        "timestamp_alignment": {
            "crypto": "single source: Binance perp D1 bars, timestamp = UTC day open, close = "
                      "23:59:59.999Z same day. Signal and target are the SAME bars -- no "
                      "cross-source alignment, no look-ahead channel.",
            "onchain_activity": "blockchain.info chart x = 00:00Z of day d, y aggregates all "
                                "blocks in day d, so the value is final at 24:00Z day d == the "
                                "Binance day-d UTC close. signal(d) -> return over (d, d+h]. "
                                "LOOK-AHEAD RISK: none structurally; residual risk is API "
                                "publication lag (the day-d point may not be queryable until "
                                "some minutes after 00:00Z d+1), which delays live use but "
                                "cannot leak future price into the screen.",
            "try_premium": "USDTTRY/BTCTRY/BTCUSDT are Binance UTC-day closes (identical "
                           "instant). Yahoo TRY=X daily bars are stamped at LONDON midnight "
                           "(23:00Z in BST, 00:00Z in GMT) and are re-dated to the London "
                           "calendar day they cover, so the FX close leads the crypto close by "
                           "0-1h -- STALE, never forward-looking. The FX-lake cross "
                           "(EURTRY/EURUSD) is a broker daily bar whose close is the ~21:00-22:00Z "
                           "rollover, i.e. 2-3h STALE vs the crypto close; it also ends "
                           "2026-06-05. Both FX legs are BACKWARD offsets: no look-ahead, only "
                           "attenuation. T3 uses no FX at all and is therefore alignment-exact.",
        },
        "trials": TRIALS + carried,
    }
    OUT.write_text(json.dumps(payload, indent=1), "utf-8")
    print(f"\n{len(TRIALS)} DSR-counted trials this pass ({len(carried)} carried forward "
          f"unchanged) -> {OUT}")
    for v in sorted({t["verdict"] for t in TRIALS}):
        print(f"  {v}: {sum(1 for t in TRIALS if t['verdict'] == v)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--axes", default=",".join(ALL_AXES),
                    help="comma-separated subset of " + ",".join(ALL_AXES))
    a = ap.parse_args()
    main(tuple(x.strip() for x in a.axes.split(",") if x.strip()))
