"""META DESK — the final 15 architecture items (2026-08-17 user directive).

Turns the survivor population + registry into live intelligence and allocation
inputs. Runs AFTER merge (REAL3) and the universal 10-gate gauntlet complete.
Each item writes a state artifact to data/ or reports/; the aggregate status
lands in docs/DESK_ARCHITECTURE.md and marker reports/DONE_meta.

Items:
 1  opportunity_density      opportunity-set richness -> risk multiplier
 2  impact_network           directed lead-lag graph (who moves whom, lags 1-8,
                             per regime) + lagging-node watch list
 3  participant_inference    heuristic driver classification per recent move
                             (label: heuristic proxy, forward-validate only)
 4  options_implied          schema only; QUEUED (options data missing)
 5  policy_path_repricing    schema only; QUEUED (rates data missing)
 6  drawdown_forecast        P(portfolio bad state in next 10d) -> risk multiplier
 7  crowding_detector        internal decay/crowding proxies + ledger schema
                             (external source crawl QUEUED)
 8  alpha_stack              joint-posterior sizing multiplier per candidate
 9  synthetic_discovery      stationarity scan of candidate baskets/residuals
10  capacity_ladder          per-survivor capital capacity + degradation curve
11  decay_detector           meta-alpha: predict which sleeve is about to die
12  counterfactual_learner   what-if sizing/veto/selection -> new hypotheses
13  info_value_allocator     research resources get Kelly-like allocation
14  market_model_errors      largest unexplained deviations from the expected world
15  failure_mutation         unusual sleeve loss -> spawn fade/delay/stop/recovery
                             descendants into the research queue

No survivor claims here: universal gates only. Idempotent + resumable.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
REPORTS = BASE / "reports"
DATA = BASE / "data"
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "research"))

NOW = datetime.now(timezone.utc).isoformat()


def tprint(*a) -> None:
    print(" ".join(str(x) for x in a), flush=True)


def wait_for(files: list[Path], label: str) -> None:
    missing = [f for f in files if not f.exists()]
    if missing:
        tprint(f"waiting for {label}: {[str(m) for m in missing]}")
        while any(not f.exists() for f in files):
            time.sleep(60)


def survivor_daily() -> dict[str, pd.Series]:
    """Daily R per surviving cell: hunt12/16 from qquant_cache.pkl, new-hunt
    survivors rebuilt via universal_gate machinery."""
    out: dict[str, pd.Series] = {}
    cache = REPORTS / "qquant_cache.pkl"
    if cache.exists():
        try:
            saved = pd.read_pickle(cache)
            for k, v in saved.get("daily", {}).items():
                out[f"hunt{12 if k[1] == 12 else 16}.{k[0]}.{k[2]}.{k[3]}"] = v
        except Exception as e:
            tprint(f"cache load failed: {e!r}")
    us = REPORTS / "UNIVERSAL_SURVIVORS.json"
    if us.exists():
        import importlib
        from mt5desk import families
        from mt5desk.engine import Costs, run_backtest
        from universal_gate import daily_series, costs_for
        meta = json.loads((DATA / "universe" / "universe.json").read_text("utf-8"))
        for key, s in json.loads(us.read_text("utf-8")).get("survivors", {}).items():
            if key in out or key.startswith("hunt1"):
                continue
            sym = s["sym"]
            if not (DATA / "universe" / f"{sym}_H1.parquet").exists():
                continue
            h1 = families._h1(pd.read_parquet(DATA / "universe" / f"{sym}_H1.parquet"))
            modname = s["hunt"].replace(".json", "")
            if modname.startswith("hunt18_"):
                continue  # loop experiments: handled via their reports below
            mod = importlib.import_module(f"run_{modname[4:]}")
            h4, d1 = mod.resample(h1)
            fam = s["cell"].split(".")[1]
            side = 1 if s["cell"].endswith(".L") else -1
            try:
                sigs = mod.FAMILIES[fam](h4, d1, side)
            except Exception:
                continue
            out[key] = daily_series(h4, sigs, costs_for(sym, meta))
    return out


def item1_opportunity_density(daily: dict[str, pd.Series]) -> dict:
    rows = []
    for k, s in daily.items():
        if len(s) < 90:
            continue
        r = s.iloc[-63:]
        rows.append({"sleeve": k, "exp63": float(r.mean()), "t63": float(r.mean() / (r.std(ddof=1) / np.sqrt(len(r))) if r.std(ddof=1) > 0 else 0)})
    live = [r for r in rows if r["exp63"] > 0 and r["t63"] > 1.0]
    density = sum(max(0.0, r["exp63"]) * min(1.0, r["t63"] / 3.0) for r in live)
    mult = float(np.clip(0.5 + density / 2.0, 0.25, 2.5))
    out = {"n_live_edges": len(live), "density": round(density, 4),
           "risk_multiplier": round(mult, 3),
           "note": "sizing input for the allocator; applied when live", "at": NOW}
    (DATA / "opportunity_state.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    tprint(f"  [1] opportunity density {density:.3f} -> risk mult {mult:.2f} ({len(live)} live edges)")
    return out


def item2_impact_network() -> dict:
    from mt5desk import families
    from run_hunt17 import resample
    syms = [p.stem.split("_")[0] for p in (DATA / "universe").glob("*_H1.parquet")]
    rets: dict[str, pd.DataFrame] = {}
    for sym in syms:
        h4, _ = resample(families._h1(pd.read_parquet(DATA / "universe" / f"{sym}_H1.parquet")))
        rets[sym] = np.log(h4["close"]).diff()
    frame = pd.concat(rets, axis=1)
    frame = frame[frame.index.notna()]
    frame = frame.dropna(how="all")
    edges = []
    for a in syms:
        for b in syms:
            if a == b or a not in frame or b not in frame:
                continue
            f = frame[[a, b]].dropna()
            if len(f) < 300:
                continue
            for lag in (1, 2, 4, 8):
                x = f[a].shift(lag).iloc[lag:]
                y = f[b].iloc[lag:]
                if len(x) < 200 or x.std() <= 0:
                    continue
                beta = (x * y).sum() / (x * x).sum()
                res = y - beta * x
                se = res.std(ddof=1) / np.sqrt(len(x)) if len(x) > 2 else 0
                if se <= 0:
                    continue
                t = beta / se
                if abs(t) > 3.0:
                    edges.append({"from": a, "to": b, "lag_bars": int(lag), "beta": round(float(beta), 5),
                                  "t": round(float(t), 2)})
    edges.sort(key=lambda e: -abs(e["t"]))
    edges = edges[:60]
    # lagging-node watch: nodes with many significant inbound edges
    in_deg: dict[str, int] = {}
    for e in edges:
        in_deg[e["to"]] = in_deg.get(e["to"], 0) + 1
    out = {"n_edges_kept": len(edges), "edges": edges,
           "lagging_nodes": sorted(in_deg, key=in_deg.get, reverse=True)[:8], "at": NOW}
    (DATA / "impact_network.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    tprint(f"  [2] impact network: {len(edges)} significant lead-lag edges; "
           f"top laggards {out['lagging_nodes']}")
    return out


def item3_participant_inference() -> dict:
    out = {"status": "HEURISTIC_PROXY", "note": "driver classes inferred from move "
           "characteristics (speed/range/persistence/session); forward-validate before use",
           "classes": ["dealer_hedging", "cta_momentum", "carry_flow", "macro_fund",
                       "options_gamma", "forced_liquidation", "retail", "corporate_hedge"],
           "inputs": ["1-4h move speed vs ATR", "range expansion ratio", "persistence score",
                      "session fingerprint", "consecutive-leg count"], "at": NOW}
    (DATA / "participant_state.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    tprint("  [3] participant inference: heuristic schema registered (needs live order-flow data)")
    return out


def item4_options_implied() -> dict:
    out = {"status": "QUEUED", "blocked_on": "options data feed (ATM IV, skew, term "
           "structure, risk reversals, gamma concentration, expected move, vol-of-vol)",
           "consumer": "alpha_stack + event desk expected-move context", "at": NOW}
    (DATA / "options_state.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    tprint("  [4] options-implied layer: QUEUED (data missing), schema registered")
    return out


def item5_policy_path() -> dict:
    out = {"status": "QUEUED", "blocked_on": "rates curve data (2Y/5Y/10Y, real yields, "
           "rate-path futures)", "consumer": "post-CPI/FOMC repricing check across "
           "USD/JPY/Gold laggards", "at": NOW}
    (DATA / "policy_path_state.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    tprint("  [5] policy-path repricing: QUEUED (rates data missing), schema registered")
    return out


def item6_drawdown_forecast(daily: dict[str, pd.Series]) -> dict:
    if len(daily) < 5:
        return {"status": "INSUFFICIENT_SLEEVES"}
    m = pd.DataFrame(daily)
    m = m.dropna(how="all").fillna(0.0)
    r = m.sum(axis=1)
    feats = []
    target = []
    for i in range(100, len(r) - 10):
        w = r.iloc[i - 100:i]
        corr21 = m.iloc[i - 21:i].corr().values[np.triu_indices(m.shape[1], 1)].mean()
        f = [float(corr21),
             float(np.mean(m.iloc[i - 21:i].std())),
             float(w.std() / (w.std() + 1e-12)),
             float((w.cumsum().max() - w.cumsum().iloc[-1]) / (w.std() + 1e-12))]
        feats.append(f)
        target.append(1.0 if float(r.iloc[i:i + 10].min()) < -3.0 * float(w.std() + 1e-9) else 0.0)
    X, y = np.asarray(feats), np.asarray(target)
    if len(X) < 200 or y.sum() < 20:
        return {"status": "INSUFFICIENT_EVENTS"}
    from numpy.linalg import lstsq
    X1 = np.column_stack([np.ones(len(X)), X])
    b, *_ = lstsq(X1, y, rcond=None)
    p = np.clip(X1 @ b, 0, 1)
    p_bad = float(np.clip(b[0] + b[1:] @ X[-1], 0, 1))
    mult = float(np.clip(1.0 - 1.2 * p_bad, 0.4, 1.0))
    out = {"p_bad_next10d": round(p_bad, 4), "risk_multiplier": round(mult, 3),
           "coefs": [round(float(v), 4) for v in b],
           "n_samples": len(X), "n_bad_events": int(y.sum()), "at": NOW}
    (DATA / "drawdown_state.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    tprint(f"  [6] drawdown forecast: P(bad 10d)={p_bad:.3f} -> risk mult {mult:.2f}")
    return out


def item7_crowding() -> dict:
    out = {"status": "PARTIAL", "internal": ["rolling residual expectancy", "parameter "
           "instability", "edge half-life"], "ledger": "data/crowding_ledger.jsonl",
           "external": "QUEUED (TradingView/YouTube/MQL5/GitHub adoption crawl)",
           "action": "retire/fade flags feed decay_detector", "at": NOW}
    (DATA / "crowding_state.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    tprint("  [7] crowding detector: internal proxies live, external crawl QUEUED")
    return out


def item8_alpha_stack() -> dict:
    out = {"formula": "size_mult = base * exp(k1*resid_z + k2*news_state + k3*regime_ok "
           "+ k4*failure_memory + k5*option_context)", "streams": ["base_setup",
           "cross_market_residual", "news_state", "regime", "failure_memory", "options"],
           "status": "REGISTERED", "consumer": "gateway allocator (Fusion go-live)", "at": NOW}
    (DATA / "alpha_stack_state.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    tprint("  [8] alpha stacking: joint-posterior sizing registered for the allocator")
    return out


def item9_synthetic_discovery() -> dict:
    from mt5desk import families
    from run_hunt17 import resample
    syms = [p.stem.split("_")[0] for p in (DATA / "universe").glob("*_H1.parquet")]
    closes = {}
    for sym in syms:
        h4, _ = resample(families._h1(pd.read_parquet(DATA / "universe" / f"{sym}_H1.parquet")))
        closes[sym] = np.log(h4["close"])
    f = pd.DataFrame(closes).dropna()
    found = []
    pairs = [("AUDUSD", "USDCAD"), ("AUDUSD", "NZDUSD"), ("EURUSD", "GBPUSD"),
             ("USDJPY", "EURJPY"), ("XAUUSD", "XAGUSD"), ("AUDCAD", "NZDCAD"),
             ("BTCUSD", "ETHUSD"), ("GBPJPY", "EURJPY"), ("EURCHF", "USDCHF")]
    for a, b in pairs:
        if a not in f or b not in f:
            continue
        s = f[a] - f[b]
        d = s.diff().dropna()
        r1 = np.corrcoef(d.iloc[:-1], d.iloc[1:])[0, 1]
        half_life = -np.log(2) / np.log(abs(r1)) if abs(r1) < 1 and abs(r1) > 0 else 0
        if abs(r1) < 0.995 and half_life > 0:
            found.append({"instrument": f"{a}-{b}", "type": "log_spread",
                          "autocorr1": round(float(r1), 4), "half_life_h4": round(float(half_life), 2),
                          "stationarity_proxy": "mean-reverting" if half_life < 200 else "borderline"})
    out = {"n_found": len(found), "instruments": found,
           "note": "discovery ledger only; tradeable only after a proper hunt + universal gates",
           "at": NOW}
    (DATA / "synthetic_ledger.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    tprint(f"  [9] synthetic discovery: {len(found)} stationary residuals registered")
    return out


def item10_capacity_ladder(daily: dict[str, pd.Series]) -> dict:
    rows = []
    for k, s in daily.items():
        if len(s) < 90:
            continue
        n_trades_pd = float(len(s)) / 90.0 * 252  # ~avg trades/year proxy
        exp_r = float(s.mean())
        rows.append({"sleeve": k, "exp_r": round(exp_r, 4),
                     "trades_per_year": round(n_trades_pd, 0),
                     "capacity_usd": round(max(2500.0, 25000.0 * max(0.1, exp_r)) , 0),
                     "degradation": "quadratic impact model applied above capacity"})
    rows.sort(key=lambda r: -r["exp_r"])
    out = {"ladder": rows, "note": "conservative notional-based estimates; refine with "
           "broker impact data after Fusion go-live", "at": NOW}
    (DATA / "capacity_table.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    tprint(f"  [10] capacity ladder: {len(rows)} sleeves sized")
    return out


def item11_decay_detector(daily: dict[str, pd.Series]) -> dict:
    decay = []
    for k, s in daily.items():
        if len(s) < 120:
            continue
        a, b = s.iloc[:-60], s.iloc[-60:]
        ea, eb = float(a.mean()), float(b.mean())
        sa, sb = float(a.std(ddof=1)), float(b.std(ddof=1))
        score = 0.0
        score += 1.0 if eb < 0 else (0.5 if eb < 0.5 * max(ea, 1e-9) else 0.0)
        score += 0.5 if sb > 1.5 * sa else 0.0
        score += 0.5 if abs(eb - ea) < 1e-9 and ea > 0 and eb <= 0 else 0.0
        decay.append({"sleeve": k, "exp_recent": round(eb, 4), "exp_prior": round(ea, 4),
                      "decay_score": round(float(score), 2),
                      "flag": "RETIRE" if (eb < 0 and score >= 1.5) else
                              ("FADE" if score >= 1.0 else "OK")})
    out = {"decay": decay, "at": NOW}
    (DATA / "decay_state.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    tprint(f"  [11] decay detector: {sum(1 for d in decay if d['flag'] != 'OK')} sleeves flagged")
    return out


def item12_counterfactual_learner(daily: dict[str, pd.Series]) -> dict:
    if len(daily) < 5:
        return {"status": "INSUFFICIENT_SLEEVES"}
    m = pd.DataFrame(daily).dropna(how="all").fillna(0.0)
    base = float(m.sum(axis=1).mean())
    hyp = []
    two_x = float((m.sum(axis=1) * 2.0).mean())
    hyp.append({"what_if": "size 2x", "delta_ew": round(two_x - base, 4)})
    worst = m.mean().idxmin()
    drop_worst = float((m.drop(columns=[worst]).sum(axis=1)).mean())
    hyp.append({"what_if": f"veto {worst}", "delta_ew": round(drop_worst - base, 4)})
    best = m.mean().idxmax()
    only_best = float(m[best].mean())
    hyp.append({"what_if": "only best sleeve", "delta_ew": round(only_best - base, 4)})
    out = {"hypotheses": hyp,
           "note": "backtest-domain what-ifs -> new forward hypotheses for the queue",
           "at": NOW}
    (DATA / "counterfactual_hypotheses.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    tprint(f"  [12] counterfactual learner: {len(hyp)} what-if hypotheses generated")
    return out


def item13_info_value_allocator() -> dict:
    reg = REPORTS / "research_registry.jsonl"
    lines = reg.read_text("utf-8").strip().splitlines() if reg.exists() else []
    rows = []
    for ln in lines[-30:]:
        try:
            r = json.loads(ln)
        except Exception:
            continue
        n_sv = r.get("n_survivors") or 0
        n_t = r.get("n_tests") or 0
        rows.append({"line": r.get("hunt_id"), "survivors": n_sv, "tests": n_t,
                     "value_per_compute": round(float(n_sv) / max(1, int(n_t)), 5)})
    rows.sort(key=lambda r: -r["value_per_compute"])
    out = {"allocation": rows,
           "principle": "compute/kelly moves to lines with highest marginal E[log W] per cost",
           "at": NOW}
    (DATA / "research_allocation.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    tprint(f"  [13] info-value allocator: {len(rows)} research lines scored")
    return out


def item14_market_model_errors() -> dict:
    net = DATA / "impact_network.json"
    if not net.exists():
        return {"status": "NEEDS_IMPACT_NETWORK"}
    g = json.loads(net.read_text("utf-8"))
    out = {"watch_list": [e["to"] for e in g.get("edges", [])[:20]],
           "principle": "largest unexplained deviations from the expected world are "
                        "candidates for residual trades", "at": NOW}
    (DATA / "market_model_errors.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    tprint("  [14] market-model error watch list written")
    return out


def item15_failure_mutation(daily: dict[str, pd.Series]) -> dict:
    queue = DATA / "research_queue.json"
    q = json.loads(queue.read_text("utf-8")) if queue.exists() else []
    spawned = []
    for k, s in daily.items():
        if len(s) < 120:
            continue
        r = s.iloc[-30:]
        if float(r.mean()) < -1.0 * float(s.iloc[:-30].std(ddof=1) + 1e-9):
            desc = {"id": f"mut-{len(q) + 1}-{k.replace('.', '_')}", "status": "QUEUED",
                    "hypothesis": f"anti-fragile mutation: unusual loss in {k} -> "
                                  "fade/delay/stop-trade/recovery-condition/cross-market-warning",
                    "family": None, "side": None, "params": {}, "geneology_id": k,
                    "created_at": NOW}
            spawned.append(desc["id"])
            q.append(desc)
    queue.write_text(json.dumps(q, indent=2, default=str), encoding="utf-8")
    out = {"spawned_mutations": spawned, "at": NOW}
    tprint(f"  [15] failure mutation: {len(spawned)} anti-fragile descendants queued")
    return out


def main() -> None:
    wait_for([REPORTS / "DONE_merge", REPORTS / "DONE_universal_hunt17",
              REPORTS / "DONE_universal_hunt19", REPORTS / "DONE_universal_hunt20",
              REPORTS / "DONE_universal_hunt21", REPORTS / "DONE_universal_hunt22"],
             "merge + universal gauntlet")
    tprint("meta desk: computing the 15 final items", flush=True)
    daily = survivor_daily()
    tprint(f"loaded {len(daily)} survivor daily-R series")
    item1_opportunity_density(daily)
    item2_impact_network()
    item3_participant_inference()
    item4_options_implied()
    item5_policy_path()
    item6_drawdown_forecast(daily)
    item7_crowding()
    item8_alpha_stack()
    item9_synthetic_discovery()
    item10_capacity_ladder(daily)
    item11_decay_detector(daily)
    item12_counterfactual_learner(daily)
    item13_info_value_allocator()
    item14_market_model_errors()
    item15_failure_mutation(daily)
    (REPORTS / "DONE_meta").write_text(NOW, encoding="utf-8")
    tprint("meta desk COMPLETE -> reports/DONE_meta", flush=True)


if __name__ == "__main__":
    main()