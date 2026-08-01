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
from libs.autodiscovery.validation import validate
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
    return {k: np.array([float(r[i]) for r in good], dtype="float64")
            for k, i in (("open", 1), ("high", 2), ("low", 3), ("close", 4))}


def _count_trades(pos: np.ndarray) -> int:
    return int(np.sum(np.abs(np.diff(pos)) > 1e-12))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default=",".join(_UNIVERSE))
    ap.add_argument("--bars", type=int, default=0, help="0 = use every bar the venue has")
    ap.add_argument("--out", default=str(_OUT))
    args = ap.parse_args(argv)

    symbols = [s.strip().upper() for s in str(args.symbols).split(",") if s.strip()]
    panel: dict[str, dict[str, np.ndarray]] = {}
    blocked: dict[str, str] = {}
    for s in symbols:
        try:
            got = fetch(s)
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
            volume=np.full(n, 1e9),
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
        v = validate(c["returns"], hypothesis=hyp, n_trials=n_trials,
                     sharpe_estimates=sharpes, returns_matrix=matrix,
                     deployed_equity_usd=25_000.0, column=i, n_trades=c["n_trades"])
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
        "source": "okx:history-candles:1D:confirmed",
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
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
