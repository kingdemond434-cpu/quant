"""Run the REAL gauntlet on the REAL history that exists, and report where every candidate dies.

WHY THIS EXISTS. Every previous campaign returned zero survivors, and the desk has repeatedly
diagnosed that from simulation rather than from a run. Two facts changed on 2026-08-01 and both
remove the excuses: the venue answers (the 403 was a User-Agent bot-block, libs/data/venue_http),
and the campaign's 310-bar window was a CHOICE -- OKX holds 2,438 confirmed daily bars for BTC.

So this runs the actual `libs.autodiscovery.validation.validate` and the actual
`libs.validation.screen_admission.admit` over the actual generator set on the full history, and
answers the only question that matters: does anything survive, and if not, WHICH GATE killed it?

THE ATTRIBUTION IS THE POINT. "Zero survivors" is not a finding, it is the absence of one. A
per-gate death count turns it into either "the mechanisms have no edge" (a real result the desk
should accept) or "one gate is eating everything" (a defect). The desk has now been wrong about
which of those it was facing at least twice, both times by reasoning instead of counting.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from libs.autodiscovery.generators import GENERATORS, net_returns
from libs.autodiscovery.models import Family, Hypothesis, MarketSeries
from libs.autodiscovery.validation import campaign_gate_stats, validate
from libs.data.venue_http import get_json
from libs.research.cohort_independence import measure, selection_amplification
from libs.validation.screen_admission import MIN_ADMISSION_BARS, admit

_ROOT = Path(__file__).resolve().parent.parent
_OUT = _ROOT / "reports" / "real_campaign.json"
_OKX = "https://www.okx.com"
_PPY = 365.0
_UNIVERSE = ("BTC", "ETH", "SOL", "DOGE", "LINK", "AVAX", "ADA", "XRP", "LTC", "BCH")


def fetch(base: str, pages: int = 30) -> dict[str, np.ndarray] | None:
    rows: list[list[str]] = []
    cursor = ""
    for _ in range(pages):
        body = get_json(f"{_OKX}/api/v5/market/history-candles?instId={base}-USDT-SWAP"
                        f"&bar=1D&limit=100{cursor}")
        page = body.get("data") or []
        if not page:
            break
        rows.extend(page)
        cursor = f"&after={page[-1][0]}"
        time.sleep(0.12)
    good = [r for r in rows if len(r) >= 9 and r[8] == "1"]
    if len(good) < 400:
        return None
    good.sort(key=lambda r: int(r[0]))
    # REAL VOLUME (2026-08-04): index 5 is base-currency volume in OKX's candle schema. The
    # flat 1e9 placeholder made every volume-reading mechanism an SMA in costume; none of the
    # incumbent 20 read volume, so this changes nothing recorded.
    return {k: np.array([float(r[i]) for r in good], dtype="float64")
            for k, i in (("open", 1), ("high", 2), ("low", 3), ("close", 4), ("volume", 5))}


#: Symbols with Binance USD-M listings <= 2020-12, so the panel carries ~5.6 YEARS at m=21.
#: Depth beats breadth at the margin (t = SR*sqrt(years); the pooling multiplier is sublinear in
#: m) -- the corrected-run declaration in NEW_FAMILY_GENERATORS_PREREGISTRATION.md has the
#: arithmetic. APT/ARB/OP/INJ are excluded for youth, not merit.
_BINANCE_UNIVERSE = ("BTC", "ETH", "SOL", "DOGE", "LINK", "AVAX", "ADA", "XRP", "LTC", "BCH",
                     "BNB", "TRX", "DOT", "NEAR", "ATOM", "UNI", "FIL",
                     "ETC", "XLM", "ALGO", "AAVE")


def fetch_binance_daily(base: str) -> dict[str, np.ndarray] | None:
    """Uniform-venue daily panel from the Binance Vision archive, REAL volume included.

    Declared in NEW_FAMILY_GENERATORS_PREREGISTRATION.md before first use: the pooled test's
    power scales with symbols per mechanism, and Vision serves full-depth daily history where
    fapi is 451-blocked. Venue is recorded in the report; OKX remains the default path."""
    from scripts.fetch_binance_vision import load_or_fetch
    d = load_or_fetch(f"{base}USDT", "1d", "2020-12", "2026-07")
    if len(d.get("open_time", ())) < 400:
        return None
    return {k: np.asarray(d[k], dtype="float64")
            for k in ("open", "high", "low", "close", "volume")}


def _count_trades(pos: np.ndarray) -> int:
    return int(np.sum(np.abs(np.diff(pos)) > 1e-12))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default=",".join(_UNIVERSE))
    ap.add_argument("--bars", type=int, default=0, help="0 = use every bar the venue has")
    ap.add_argument("--out", default=str(_OUT))
    ap.add_argument("--venue", default="okx", choices=("okx", "binance-vision"))
    args = ap.parse_args(argv)
    if args.venue == "binance-vision" and args.symbols == ",".join(_UNIVERSE):
        args.symbols = ",".join(_BINANCE_UNIVERSE)

    symbols = [s.strip().upper() for s in str(args.symbols).split(",") if s.strip()]
    panel: dict[str, dict[str, np.ndarray]] = {}
    blocked: dict[str, str] = {}
    for s in symbols:
        try:
            got = fetch_binance_daily(s) if args.venue == "binance-vision" else fetch(s)
            if got is None:
                blocked[s] = "fewer than 400 confirmed daily bars"
            else:
                panel[s] = got
        except Exception as exc:
            blocked[s] = str(exc)
    if not panel:
        raise SystemExit(f"no symbols fetched: {blocked}")

    btc = panel.get("BTC")

    # --- build every candidate, score it, collect the cohort ------------------------------
    cands: list[dict[str, Any]] = []
    for sym, raw in sorted(panel.items()):
        n = len(raw["close"])
        if args.bars:
            raw = {k: v[-args.bars:] for k, v in raw.items()}
            n = len(raw["close"])
        ref = None
        if btc is not None and sym != "BTC":
            m = min(n, len(btc["close"]))
            ref = {k: btc[k][-m:] for k in btc}
            raw = {k: v[-m:] for k, v in raw.items()}
            n = m
        ser = MarketSeries(
            close=raw["close"], high=raw["high"], low=raw["low"],
            volume=raw.get("volume", np.full(n, 1e9)),
            hour=np.zeros(n),
            ref_close=ref["close"] if ref else None,
            ref_high=ref["high"] if ref else None,
            ref_low=ref["low"] if ref else None,
        )
        for spec in GENERATORS:
            for variant in spec.param_variants:
                try:
                    pos = np.asarray(spec.fn(ser, dict(variant)), dtype="float64")
                except Exception:
                    continue
                if pos.size == 0 or float(np.mean(pos != 0.0)) < 0.01:
                    continue
                r = net_returns(ser, pos)
                if not np.all(np.isfinite(r)) or float(np.std(r)) <= 0:
                    continue
                cands.append({
                    "symbol": sym, "family": spec.family, "subtype": spec.subtype,
                    "params": dict(variant), "returns": r, "n_bars": n,
                    "n_trades": _count_trades(pos),
                    "mechanism": spec.mechanism, "edge_source": spec.edge_source,
                    "failure_modes": list(spec.failure_modes),
                })

    if not cands:
        raise SystemExit("no scorable candidates")

    T = min(len(c["returns"]) for c in cands)
    matrix = np.column_stack([c["returns"][-T:] for c in cands])
    sharpes = np.array([float(np.mean(c["returns"]) / np.std(c["returns"], ddof=1))
                        for c in cands])
    n_trials = len(cands)

    # PER-CANDIDATE CAMPAIGN STATISTICS, and this is a correction rather than a loosening.
    #
    # MEASURED 2026-08-01, first run: dsr killed 196 of 196 and reality_check killed 196 of 196.
    # A gate with a 100% rejection rate is not a filter, it has no discriminating power at all --
    # so the question is which of the two it is, and it was both.
    #
    # `validate` takes the corrected path only when a CampaignGates is supplied. This script
    # passed `column=i` but never `campaign=`, so `per_candidate` was False and it fell to the
    # LEGACY branch, which pays the multiplicity penalty TWICE: the full DSR deflation over
    # n_trials AND White's Reality Check over the same N. That is exactly the doubled family-wise
    # bar audit R0224 measured as costing up to 78 points of power (5.8% -> 83.8% at true SR 5.0,
    # with false positives at 0 of 4,800 either way). The fix shipped in validation.py; this
    # caller simply never opted into it.
    #
    # The legacy branch also broadcasts ONE cohort verdict to every candidate --
    # whites_reality_check returns a single p-value for the whole matrix -- which is why the death
    # count was exactly 196 and not 196 independent judgements. Romano-Wolf step-down still
    # controls family-wise error across all N, so multiplicity is paid in full, once, and each
    # candidate earns its own verdict instead of inheriting the cohort's.
    gates_stats = campaign_gate_stats(matrix)

    # --- run the REAL gauntlet ------------------------------------------------------------
    deaths: dict[str, int] = {}
    rows: list[dict[str, Any]] = []
    admit_rows: list[dict[str, object]] = []
    for i, c in enumerate(cands):
        hyp = Hypothesis(
            family=Family(c["family"]), subtype=c["subtype"], symbol=c["symbol"],
            params=c["params"], mechanism=c["mechanism"], edge_source=c["edge_source"],
            failure_modes=c["failure_modes"],
        )
        # _PPY is this campaign's own clock (D1 crypto, 24/7) and it now reaches the STORE, not
        # just this script's artifact: the report always computed its own honest figure while
        # validate() annualised the same series with an hourly constant (R0086).
        v = validate(c["returns"], hypothesis=hyp, periods_per_year=_PPY, n_trials=n_trials,
                     sharpe_estimates=sharpes, returns_matrix=matrix,
                     column=i, n_trades=c["n_trades"],
                     campaign=gates_stats)
        gates = dict(v.gates)
        for g, ok in gates.items():
            if not ok:
                deaths[g] = deaths.get(g, 0) + 1
        name = f"{c['symbol']}:{c['subtype']}:{'/'.join(f'{k}={vv:g}' for k, vv in c['params'].items())}"
        ann = float(np.mean(c["returns"]) / np.std(c["returns"], ddof=1) * np.sqrt(_PPY))
        rows.append({"name": name, "family": str(c["family"]), "n_bars": c["n_bars"],
                     "n_trades": c["n_trades"], "in_sample_ann_sharpe": ann,
                     "oos_sharpe": v.metrics.oos_sharpe,
                     "failed_gates": sorted(g for g, ok in gates.items() if not ok),
                     "unmeasured": list(v.unmeasured)})
        admit_rows.append({"name": name, "gates": gates,
                           "oos_sharpe": v.metrics.oos_sharpe,
                           "dsr": v.metrics.dsr, "reality_p": v.metrics.reality_p,
                           "n_bars": c["n_bars"], "cost_basis": "net"})

    plan = admit(admit_rows, idle_slots=12, cost_basis="net")
    survivors = [r for r in rows if not r["failed_gates"]]

    # --- THE POOLED-BY-MECHANISM PATH: the view that can actually certify a survivor ---------
    #
    # MEASURED 2026-08-01 (docs/research/REALITY_CHECK_POWER.md, reports/reality_check_audit.json):
    # at this campaign's N=196 and T=2,018 the reality_check gate's power at a TRUE annualised
    # Sharpe of 1.0 is 5%, and the closed-form minimum detectable Sharpe is 1.48 -- above the
    # desk's entire measured real-edge band (0.5-1.5). The gate is CORRECT (false positives
    # 0/3,900); the DESIGN asks it an unanswerable question by testing `mom[40] on BTC`,
    # `mom[40] on ETH`, ... as ten separate hypotheses. Pooling the SAME mechanism's returns
    # equal-weight across symbols asks the right one: "does this mechanism work on crypto" is one
    # hypothesis with ten symbols of evidence. At the MEASURED same-mechanism cross-symbol
    # strategy correlation of 0.348, ten symbols give 2.42x effective observations (1.56x on the
    # t-statistic) while N falls from 196 to ~the mechanism count -- power at SR 1.0 goes 5%->70%
    # and the detection floor moves to 0.77, INSIDE the band. Alpha untouched, gates untouched.
    #
    # NOT FREE, AND SAID SO: a mechanism that works on two symbols and fails on eight is diluted
    # by the average and correctly dies -- pooling tests a strictly STRONGER claim than any
    # per-symbol test. That is the intended behaviour. The per-symbol view above keeps its
    # diagnostic value; this view is the certification path.
    groups: dict[tuple, list[dict[str, Any]]] = {}
    for c in cands:
        key = (str(c["family"]), c["subtype"], tuple(sorted(c["params"].items())))
        groups.setdefault(key, []).append(c)
    pooled: list[dict[str, Any]] = []
    for _key, members in sorted(groups.items(), key=lambda kv: str(kv[0])):
        if len(members) < 2:
            continue        # one symbol pools nothing; the per-symbol row already covers it
        stack = np.column_stack([m["returns"][-T:] for m in members])
        pr = stack.mean(axis=1)
        if float(np.std(pr)) <= 0:
            continue
        proto = members[0]
        pooled.append({
            "family": proto["family"], "subtype": proto["subtype"],
            "params": dict(proto["params"]),
            "returns": pr, "n_symbols": len(members),
            "symbols": sorted(m["symbol"] for m in members),
            # trades summed across legs: the pooled book actually takes all of them
            "n_trades": int(sum(m["n_trades"] for m in members)),
            "mechanism": proto["mechanism"], "edge_source": proto["edge_source"],
            "failure_modes": list(proto["failure_modes"]),
        })

    pooled_doc: dict[str, Any] = {"n_mechanisms": len(pooled)}
    pooled_survivors: list[dict[str, Any]] = []
    if pooled:
        p_matrix = np.column_stack([p["returns"] for p in pooled])
        p_sharpes = np.array([float(np.mean(p["returns"]) / np.std(p["returns"], ddof=1))
                              for p in pooled])
        p_stats = campaign_gate_stats(p_matrix)
        p_deaths: dict[str, int] = {}
        p_rows: list[dict[str, Any]] = []
        for i, p in enumerate(pooled):
            hyp = Hypothesis(
                family=Family(p["family"]), subtype=p["subtype"],
                symbol=f"POOLED[{p['n_symbols']}]",
                params=p["params"], mechanism=p["mechanism"], edge_source=p["edge_source"],
                failure_modes=p["failure_modes"],
            )
            v = validate(p["returns"], hypothesis=hyp, periods_per_year=_PPY,
                         n_trials=len(pooled),
                         sharpe_estimates=p_sharpes, returns_matrix=p_matrix,
                         column=i, n_trades=p["n_trades"],
                         campaign=p_stats)
            for g, ok in v.gates.items():
                if not ok:
                    p_deaths[g] = p_deaths.get(g, 0) + 1
            name = (f"POOLED:{p['subtype']}:"
                    f"{'/'.join(f'{k}={vv:g}' for k, vv in p['params'].items())}")
            ann = float(p_sharpes[i] * np.sqrt(_PPY))
            row = {"name": name, "family": str(p["family"]),
                   "n_symbols": p["n_symbols"], "symbols": p["symbols"],
                   "n_trades": p["n_trades"], "in_sample_ann_sharpe": ann,
                   "oos_sharpe": v.metrics.oos_sharpe, "dsr": v.metrics.dsr,
                   "reality_p": v.metrics.reality_p, "pbo": v.metrics.pbo,
                   "failed_gates": sorted(g for g, ok in v.gates.items() if not ok),
                   "unmeasured": list(v.unmeasured)}
            p_rows.append(row)
            if not row["failed_gates"]:
                pooled_survivors.append(row)
        pooled_doc.update({
            "note": ("ONE hypothesis per mechanism, tested against the equal-weight average of "
                     "its per-symbol returns; a strictly stronger claim than any per-symbol "
                     "test. Power at true ann. Sharpe 1.0: 70% here vs 5% per-symbol at N=196 "
                     "(reports/reality_check_audit.json)."),
            "deaths_by_gate": dict(sorted(p_deaths.items(), key=lambda kv: -kv[1])),
            "n_clearing_every_gate": len(pooled_survivors),
            "survivors": pooled_survivors,
            "rows": sorted(p_rows, key=lambda r: -(r["oos_sharpe"] or -9)),
        })

    # IS THE ADMITTED SET ONE BET IN MANY COSTUMES? Measured on the set admission ACTUALLY
    # returned, not on the candidate pool and not on a top-k proxy. The pool's correlation is the
    # number this desk has been reading and it is beside the point -- nothing trades the pool. On
    # the 2026-08-01 fifty-one-strategy cohort the pool sat at 0.08, comfortably better than the
    # 0.159 professional benchmark, while the candidates that won sat at 0.85.
    by_name = {r["name"]: i for i, r in enumerate(rows)}
    admitted_cols = np.array([by_name[a.name] for a in plan.admitted if a.name in by_name],
                             dtype=int)
    sel = selection_amplification(matrix, sharpes, k=max(len(admitted_cols), 2),
                                  selected=admitted_cols if admitted_cols.size else None)

    doc = {
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "status": "MEASURED",
        "source": ("binance-vision:1d:monthly-archive" if args.venue == "binance-vision"
                   else "okx:history-candles:1D:confirmed"),
        "symbols": sorted(panel), "blocked_symbols": blocked,
        "bars_per_symbol": {s: len(v["close"]) for s, v in sorted(panel.items())},
        "min_admission_bars": MIN_ADMISSION_BARS,
        "n_candidates": len(cands), "n_trials_priced": n_trials,
        "n_clearing_every_gate": len(survivors),
        "deaths_by_gate": dict(sorted(deaths.items(), key=lambda kv: -kv[1])),
        "admitted": [{"name": a.name, "rank": a.rank_score} for a in plan.admitted],
        "admission_notes": list(plan.notes),
        "pool_independence": measure(matrix).summary(),
        "selection_effect": {"summary": sel.summary(), "pool_corr": sel.pool_corr,
                             "selected_corr": sel.selected_corr, "p_value": sel.p_value,
                             "n_eff_pool": sel.n_eff_pool,
                             "n_eff_selected": sel.n_eff_selected,
                             "verdict": sel.verdict},
        "top_by_oos": sorted(rows, key=lambda r: -(r["oos_sharpe"] or -9))[:15],
        "survivors": survivors[:40],
        "pooled_by_mechanism": pooled_doc,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, default=str), "utf-8")
    print(json.dumps({k: doc[k] for k in (
        "n_candidates", "n_clearing_every_gate", "deaths_by_gate", "bars_per_symbol")},
        indent=2, default=str))
    print(f"admitted: {[a.name for a in plan.admitted]}")
    print(f"pool:      {doc['pool_independence']}")
    print(f"selection: {sel.summary()}")
    print(f"POOLED: {pooled_doc.get('n_mechanisms', 0)} mechanisms, "
          f"{pooled_doc.get('n_clearing_every_gate', 0)} clearing every gate; "
          f"deaths {pooled_doc.get('deaths_by_gate', {})}")
    for s in pooled_survivors:
        print(f"  POOLED SURVIVOR: {s['name']}  ann_sharpe={s['in_sample_ann_sharpe']:.2f} "
              f"oos={s['oos_sharpe']}  p={s['reality_p']:.4f}  over {s['n_symbols']} symbols")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
