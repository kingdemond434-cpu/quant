"""SCOPED GENERATE RUN -- fred_macro family (owed item, docs/research/generation_due.md line 5).

WHAT WAS ACTUALLY OWED, AND WHAT WAS ALREADY PAID
-------------------------------------------------
`generation_due.md` is a 2026-07-16 SNAPSHOT and was never regenerated. The cadence engine's own
condition (scripts/run_cadence.py:202) is

    Path("data/fred_macro.json").exists() and not state.get("gen_done_fred_macro_family")

and `data/cadence_state.json` has carried `gen_done_fred_macro_family = 2026-07-17T08:55:24Z`
since the day after the snapshot. So the PAPER duty (author + EV-gate pre-registrations) is
closed and the flag is stale. What was never done is the part the flag's own justification
promised -- "deep history available ... immediately backtestable against the crypto lake": not one
fred_macro series has ever been put through the audited Stage-A harness. This run does that.

THE HONEST PRIOR, STATED UP FRONT (this run does not get to pretend it is exploring virgin ground)
--------------------------------------------------------------------------------------------------
The macro->crypto class has been EV-rejected SIX times by this desk: 3 FRED-family overlays on
2026-07-17 (EV 0.004-0.013), then `dxy_shock_beta_rotation` (fx, 0.0052), `risk_regime_rotation`
(index, 0.0027) and `net_liquidity_impulse` (fed, 0.0026) on 2026-07-22 -- the last carrying the
note "if it also rejects, the fed axis is ledgered exhausted". It rejected. Those are ECONOMIC
priors, not measurements: nobody ever looked. Screening is the empirical complement, run at the
SAME bar, and it cannot reopen the EV verdict -- Stage A has zero promotion authority and no cell
here is passed a `clock=`, so nothing on this axis can start a forward clock no matter how it
prints. A "good" IC here would be a finding to report, never a decision.

PRE-DECLARED POWER VERDICT (computed from sample LENGTH alone, before any IC is seen)
-------------------------------------------------------------------------------------
stage_a_screen calls a cell powered only when 1.96/sqrt(n_eff) <= ic_min=0.03, i.e. it needs
n_eff >= 4268 independent observations. The deepest fred_macro series aligned to BTC gives ~4030
US business days (DTWEXBGS from 2006-01, VIXCLS from 1990-01, both clipped by BTC history starting
2010-07), and n_eff is then divided again by the mean calendar spacing. EVERY cell in this run is
therefore expected to return SCREEN-UNDERPOWERED, at every horizon, before a single number is
computed. They are run anyway -- the ICs are recorded evidence a later meta-analysis can pool, and
"we never looked" is the exact defect the data-utilization law exists to kill -- but they are
counted as trials and NOT reported as if the null were a refutation.

Deliberately NOT screened, with reasons (declared, not silently dropped):
  * M2SL -- monthly (~192 obs once aligned to BTC), ~25-day publication lag, AND FRED serves the
    CURRENT VINTAGE of a series that is revised. A backtest on current-vintage M2 uses numbers
    that were not knowable at the time: look-ahead THROUGH REVISION, which no timestamp alignment
    can fix. Untestable honestly from this archive.

TIMESTAMP ALIGNMENT (declared per series; every one is a BACKWARD/stale offset except WALCL,
whose forward release lag is handled by an explicit lag)
--------------------------------------------------------------------------------------------------
  crypto leg  Coin Metrics community daily BTC close, PriceUSD dated d == fixed close at 00:00 UTC
              on d+1. VERIFIED against the Binance D1 lake on the 2515 overlapping days: same-date
              log-return corr +0.994, and shifting either leg one day collapses it to
              -0.047 / -0.066. Same date label = same instant.
  DGS10,
  T10Y2Y      Treasury H.15 constant-maturity yields struck ~15:30 ET on business day d, published
              ~16:15 ET the same day => 3.5-4.5h STALE vs the 00:00Z d+1 crypto close. BACKWARD.
  VIXCLS      CBOE VIX official close 16:15 ET day d, published same day => ~3h STALE. BACKWARD.
  DTWEXBGS    Fed H.10 broad dollar index, NOON ET buying rates on day d, published ~16:15 ET day
              d => ~7h STALE. BACKWARD.
  WALCL       H.4.1 balance sheet AS OF Wednesday d but RELEASED Thursday 16:30 ET. The value
              dated d is NOT knowable at the day-d close. LOOK-AHEAD RISK: REAL, and it is the
              only one in this run. Handled by shifting the series +2 calendar days before any
              alignment, so the signal is first used at the d+2 close -- strictly after the
              release. WALCL is an accounting statement and is not materially revised.

SAMPLING: FRED observation dates INTERSECT BTC dates; the target is the BTC return between
CONSECUTIVE SAMPLED dates, so a Friday->Monday step is a 3-calendar-day return. `horizon_days`
passed to the harness is the MEAN realised calendar spacing of the sampled blocks, so the Sharpe
annualisation sqrt(365/h) matches the actual period and n_eff is if anything under-credited
(non-overlapping blocks need no overlap correction at all). Blocks are non-overlapping, so
signal[k] is observed strictly inside period k and predicts period k+1.

    .venv/bin/python scripts/screen_fred_macro_axis.py
"""
from __future__ import annotations

import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.screen_idle_axes import _graveyard_priors, block_idx  # noqa: E402

from libs.alpha_factory.hypothesis_novelty import PriorIdea, hypothesis_novelty  # noqa: E402
from libs.research.alpha_economics import Idea, ev_score  # noqa: E402
from libs.research.axis_screen import stage_a_screen  # noqa: E402

OUT = ROOT / "data/fred_macro_screen.json"
DEEP = ROOT / "data/fred_macro_deep.json"
FRED = "https://api.stlouisfed.org/fred/series/observations"
ZWIN = {1: 20, 5: 12, 20: 6}
TRIALS: list[dict] = []


# ------------------------------------------------------------------- candidate pre-registrations
# (series, name, mechanism, construction, horizons, novelty features, EV Idea)
CANDIDATES = [
    ("DTWEXBGS", "dollar_funding_squeeze",
     "The broad trade-weighted dollar is the numeraire of global dollar FUNDING, not just a "
     "relative price. A sharp broad-dollar appreciation raises the cost of the offshore dollar "
     "borrowing that levered carry runs on, and levered carry unwinds are forced, not "
     "discretionary -- so a dollar squeeze should push a marginal, highly levered dollar-funded "
     "asset class down with a short lag.",
     "signal = 5-business-day log change in DTWEXBGS (a squeeze is a MOVE, not a level), "
     "z-scored by the harness; target = absolute BTC return over the next block. Absolute, not "
     "cross-sectional, because a funding shock is market-wide and has no asset-selection content.",
     (1, 5, 20), ("broad_dollar_shock", "dollar_funding", "btc_timing", "macro_overlay"),
     Idea(name="dollar_funding_squeeze", est_sharpe=0.3, breadth=1, capacity_usd=2e6,
          orthogonality=0.6, effort_h=6.0, tags=["new_orthogonal_data", "crowded_known"])),

    ("WALCL", "reserve_quantity_impulse",
     "The Fed's balance sheet is the QUANTITY of system reserves. Reserve creation/destruction is "
     "an inelastic quantity constraint on the marginal dollar available to bid risk assets -- a "
     "structural mechanism, not a sentiment read -- and the highest-beta sink for that marginal "
     "dollar should respond over weeks, the speed at which reserves actually settle through.",
     "signal = 4-week log change in WALCL, series LAGGED +2 calendar days for the Thursday "
     "16:30 ET H.4.1 release; target = absolute BTC return between consecutive weekly samples.",
     (1, 5), ("fed_balance_sheet", "reserve_quantity", "btc_timing", "liquidity_impulse"),
     Idea(name="reserve_quantity_impulse", est_sharpe=0.3, breadth=1, capacity_usd=2e6,
          orthogonality=0.5, effort_h=6.0, tags=["crowded_known"])),

    ("VIXCLS", "equity_vol_deleveraging",
     "VIX is the price of equity tail insurance and the input that mechanical vol-target and "
     "risk-parity books size on. A VIX spike mechanically shrinks their risk budget, and the "
     "highest-beta sleeve is cut first -- so the deleveraging is a forced flow, not a mood.",
     "signal = VIXCLS level, z-scored by the harness; target = absolute BTC return over the next "
     "block.",
     (1, 5, 20), ("equity_implied_vol", "risk_appetite", "btc_timing", "vol_target_deleveraging"),
     Idea(name="equity_vol_deleveraging", est_sharpe=0.3, breadth=1, capacity_usd=2e6,
          orthogonality=0.4, effort_h=6.0, tags=["crowded_known"])),

    ("T10Y2Y", "curve_slope_policy_path",
     "The 2s10s slope is the market's forward read of the policy path; a steepening driven by the "
     "front end prices expected easing, i.e. future reserve creation, ahead of the fact. A "
     "liquidity-sensitive asset should discount that path before the reserves arrive.",
     "signal = T10Y2Y level, z-scored by the harness; target = absolute BTC return over the next "
     "block.",
     (5, 20), ("yield_curve_slope", "policy_path", "btc_timing", "macro_overlay"),
     Idea(name="curve_slope_policy_path", est_sharpe=0.25, breadth=1, capacity_usd=2e6,
          orthogonality=0.5, effort_h=6.0, tags=["crowded_known"])),

    ("DGS10", "nominal_yield_opportunity_cost",
     "The 10y nominal yield is the opportunity cost of parking capital in a zero-cashflow "
     "store-of-value. When the risk-free alternative pays more, the hurdle for holding a "
     "non-yielding asset rises and the marginal allocator rotates out.",
     "signal = DGS10 level, z-scored by the harness; target = absolute BTC return over the next "
     "block.",
     (5, 20), ("nominal_yield", "opportunity_cost", "btc_timing", "macro_overlay"),
     Idea(name="nominal_yield_opportunity_cost", est_sharpe=0.25, breadth=1, capacity_usd=2e6,
          orthogonality=0.5, effort_h=6.0, tags=["crowded_known"])),
]

NOT_SCREENED = {
    "M2SL": "monthly (~192 obs once aligned to BTC), ~25-day publication lag, and FRED serves the "
            "CURRENT VINTAGE of a REVISED series -- a backtest would use numbers that were not "
            "knowable at the time (look-ahead through revision, which no alignment can fix). "
            "Untestable honestly from this archive; NOT a null result. "
            "STATUS CHANGED 2026-08-12 (R0316): the blocker is no longer structural, it is a "
            "SAMPLE. collect_fred_macro now records every vintage to libs.research.vintage, so "
            "libs.research.vintage.as_of(root, 'M2SL', d) answers what was knowable on d. The "
            "history starts 2026-08-12 and cannot be back-filled, so this stays excluded until "
            "the store spans the test window -- and the release condition is EVIDENCE, not a "
            "date (L1.48): re-open when vintage.summarise reads OK rather than ACCRUING and the "
            "covered span reaches the intended sample. Screening it before then would read "
            "today's restatements as contemporaneous knowledge, which is the exact leak this "
            "exclusion exists to prevent.",
}


# ------------------------------------------------------------------------------------- priors ---
def _prereg_priors() -> list[PriorIdea]:
    """The EV-rejected pre-registration cards -- the NEAREST priors to anything macro->crypto.

    The graveyard alone does not contain them (they died at the EV gate, before compute), so a
    novelty gate that only reads the graveyard would call a sixth macro overlay 'novel'.
    """
    txt = (ROOT / "docs/research/AXIS_PREREGISTRATIONS.md").read_text("utf-8")
    out: list[PriorIdea] = []
    for block in txt.split("\n### ")[1:]:
        head, _, body = block.partition("\n")
        m = re.match(r"(\S+)\s*\(([^)]+)\)", head.strip())
        if not m:
            continue
        out.append(PriorIdea(id=f"prereg:{m.group(1)}", category=m.group(2),
                             statement=body.replace("\n", " ")[:1500],
                             lesson="EV-gate REJECT before compute; the class is ledgered"))
    return out


def novelty(name: str, statement: str, features: tuple[str, ...]) -> dict:
    priors = _graveyard_priors() + _prereg_priors()
    r = hypothesis_novelty(statement, features=features, priors=priors)
    out = {"candidate": name, "novelty_score": round(r.novelty_score, 3),
           "nearest_id": r.nearest_id, "nearest_similarity": round(r.nearest_similarity, 3),
           "is_redundant": r.is_redundant, "nearest_lesson": (r.nearest_lesson or "")[:160],
           "n_priors": len(priors)}
    print(f"  NOVELTY {name:34s} score {out['novelty_score']:<6} "
          f"nearest={out['nearest_id']} sim={out['nearest_similarity']} "
          f"redundant={out['is_redundant']}")
    return out


# --------------------------------------------------------------------------------------- data ---
def fred_deep(sid: str, key: str) -> pd.Series:
    q = urllib.parse.urlencode({"series_id": sid, "api_key": key, "file_type": "json",
                                "observation_start": "1900-01-01"})
    req = urllib.request.Request(f"{FRED}?{q}", headers={"User-Agent": "quant-fred-screen/1.0"})
    with urllib.request.urlopen(req, timeout=45) as r:
        obs = json.loads(r.read()).get("observations", [])
    d = {pd.Timestamp(o["date"], tz="UTC"): float(o["value"])
         for o in obs if o.get("value") not in (".", "", None)}
    return pd.Series(d).sort_index()


def coinmetrics_btc() -> pd.Series:
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


# -------------------------------------------------------------------------------------- screen ---
def cell(name: str, sid: str, sig: np.ndarray, ret: np.ndarray, h: int, span_days: np.ndarray,
         extra: dict) -> dict:
    """One DSR-counted trial. Recorded whatever it prints -- including the certain-underpowered."""
    hd = float(np.mean(span_days)) * h
    r = stage_a_screen(sig, ret, name=f"fred_macro::{name}::h{h}b", zwin=ZWIN[h], horizon_days=hd)
    r.update({"axis": "fred_macro", "series": sid, "construction": name,
              "blocks_of_business_days": h, "mean_calendar_days_per_block": round(hd, 3),
              "zwin": ZWIN[h], "target_kind": "absolute BTC timing return", **extra})
    TRIALS.append(r)
    print(f"  {name:32s} h={h:2d}b({hd:5.1f}d) n={r.get('n'):5d} IC={r.get('ic'):+.4f} "
          f"same={r.get('same_period_corr'):+.3f} resid={r.get('residual_ic'):+.4f} "
          f"momSh={r.get('sharpe_momentum'):+.2f} n_eff={r.get('n_eff')} "
          f"mdi={r.get('min_detectable_ic')} pw={r.get('powered')} -> {r['verdict']}")
    return r


def transform(sid: str, s: pd.Series) -> pd.Series:
    """The pre-declared construction per series (see CANDIDATES)."""
    if sid == "DTWEXBGS":
        return np.log(s).diff(5).dropna()                    # 5-business-day dollar move
    if sid == "WALCL":
        lagged = pd.Series(s.to_numpy(), index=s.index + pd.Timedelta(days=2))   # release lag
        return np.log(lagged).diff(4).dropna()               # 4-week reserve impulse
    return s.dropna()                                        # levels: VIXCLS / T10Y2Y / DGS10


def main() -> None:
    key = json.loads((ROOT / "data/secrets/fred.json").read_text("utf-8"))["key"]
    btc = coinmetrics_btc()
    print(f"BTC leg (coinmetrics daily close): n={len(btc)} "
          f"{btc.index.min().date()} -> {btc.index.max().date()}\n")

    print("=" * 100)
    print("NOVELTY GATE (before compute) -- graveyard + live sleeves + EV-rejected prereg cards")
    print("=" * 100)
    nov = {c[1]: novelty(c[1], f"{c[2]} {c[3]}", c[5]) for c in CANDIDATES}

    print("\n" + "=" * 100)
    print("EV GATE (pre-registered, honest inputs, no tuning-to-pass)")
    print("=" * 100)
    ev = {}
    for c in CANDIDATES:
        e = ev_score(c[6])
        ev[c[1]] = e
        print(f"  EV {c[1]:34s} {e['ev']:<8} p_survive={e['p_survive']:<7} -> {e['verdict']}")

    deep: dict[str, list] = {}
    print("\n" + "=" * 100)
    print("STAGE-A SCREENS (audited harness, artifact gate baked in, NO clock passed on any cell)")
    print("=" * 100)
    for sid, name, mech, _constr, horizons, _feat, _idea in CANDIDATES:
        raw = fred_deep(sid, key)
        deep[sid] = [[d.strftime("%Y-%m-%d"), v] for d, v in raw.items()]
        s = transform(sid, raw)
        common = s.index.intersection(btc.index)
        if len(common) < 60:
            TRIALS.append({"axis": "fred_macro", "series": sid, "construction": name,
                           "verdict": "INSUFFICIENT-DATA", "n": len(common),
                           "note": f"{len(common)} aligned obs < 60"})
            print(f"  {name}: only {len(common)} aligned obs -- INSUFFICIENT-DATA")
            continue
        sv = s.reindex(common).to_numpy()
        bv = btc.reindex(common).to_numpy()
        gap = np.diff(common.to_numpy().astype("datetime64[D]").astype(int))
        print(f"\n  {sid} raw n={len(raw)} {raw.index.min().date()}->{raw.index.max().date()} | "
              f"aligned {len(common)} obs {common.min().date()}->{common.max().date()} | "
              f"mean spacing {gap.mean():.2f}d")
        print(f"    mechanism: {mech[:150]}")
        for h in horizons:
            idx = block_idx(len(common), h)
            b_h = bv[idx]
            ret_h = np.zeros(len(idx))
            ret_h[1:] = b_h[1:] / b_h[:-1] - 1.0
            cell(name, sid, sv[idx], ret_h, h, gap,
                 {"aligned_obs": len(common), "n_blocks": len(idx),
                  "mdi_block": round(float(1.96 / np.sqrt(max(len(idx), 1))), 4),
                  "span": f"{common.min().date()}..{common.max().date()}",
                  "novelty": nov[name], "ev": ev[name]})

    DEEP.write_text(json.dumps({"updated": datetime.now(tz=UTC).isoformat(),
                                "note": "deep FRED history fetched for RESEARCH only -- the daily "
                                        "collector (scripts/collect_fred_macro.py, 1200d window) "
                                        "and web/fred_macro.json are untouched",
                                "series": deep}, indent=1), "utf-8")
    payload = {
        "updated": datetime.now(tz=UTC).isoformat(),
        "stage": "A (zero promotion authority) -- no cell was passed a clock; none can start one",
        "duty": "generation_due.md line 5 -- fred_macro family scoped generate run",
        "cadence_note": "gen_done_fred_macro_family has been set since 2026-07-17T08:55:24Z; the "
                        "generation_due.md snapshot (2026-07-16) is stale. The PAPER duty was "
                        "closed then; this run adds the empirical screens that were never done.",
        "prior_ev_rejections": "macro->crypto EV-rejected 6x: 3 FRED overlays 2026-07-17 "
                               "(0.004-0.013); dxy_shock_beta_rotation 0.0052, "
                               "risk_regime_rotation 0.0027, net_liquidity_impulse 0.0026 "
                               "(2026-07-22, 'fed axis ledgered exhausted').",
        "timestamp_alignment": __doc__.split("TIMESTAMP ALIGNMENT")[1].split("SAMPLING")[0].strip(),
        "sampling": __doc__.split("\nSAMPLING:")[1].split("\n\n")[0].strip(),
        "not_screened": NOT_SCREENED,
        "novelty_gate": list(nov.values()),
        "ev_gate": list(ev.values()),
        "trials": TRIALS,
    }
    OUT.write_text(json.dumps(payload, indent=1), "utf-8")
    print(f"\n{len(TRIALS)} DSR-counted trials -> {OUT}")
    for v in sorted({t["verdict"] for t in TRIALS}):
        print(f"  {v}: {sum(1 for t in TRIALS if t['verdict'] == v)}")
    print(f"  deep FRED history archived -> {DEEP}")


if __name__ == "__main__":
    main()
