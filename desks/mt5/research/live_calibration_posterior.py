#!/usr/bin/env python3
"""LIVE ATTRIBUTION AS THE FINAL JUDGE: the posterior on how much each producer's claims are worth
(Tier-1 audit item #17, 2026-09-29).

THE PRINCIPAL: "Live attribution the final judge: expected vs realised edge, slippage,
correlation, drawdown, marginal contribution; Bayesian posteriors update continuously; research
priors that overstate live get downweighted automatically."

WHAT ALREADY EXISTS AND WHAT IT DOES NOT DO.
  * `allocator_attribution.py` decomposes the BOOK's miss into edge / correlation / execution /
    regime / tail -- per book, per day. It does not say which PRODUCER's claims were inflated.
  * `credit_assignment.py` walks live -> sleeve -> certificate -> scientist and credits REALISED
    R, and `libs/research/bandit.realised_credit` turns it into an arm factor. Realised R rewards
    a producer that found a big edge; it cannot tell a producer whose certificates promised 0.30
    and delivered 0.30 from one that promised 0.90 and delivered 0.30. The second is overstating,
    and its NEXT certificates deserve less of the research budget than its realised R suggests.
  * `edge_reliability.py` fuses declared factors per sleeve; it says itself it is not a
    posterior and nothing reads it.

WHAT THIS IS. For every certificate with realised evidence, the ratio the principal asked for:

    s_i  = realised Sharpe per trading day  (live when the sleeve has >= MIN_LIVE_TRADES deals,
                                              forward clock otherwise -- and every row says which)
    e_i  = the certificate's own claimed Sharpe per day (walk-forward OOS, then CPCV, lockbox,
           in-sample -- the first one the certificate carries)

and, per producer p, a conjugate Normal posterior on the calibration ratio kappa_p:

    s_i | kappa_p  ~  N(kappa_p * e_i,  1 / N_i)        N_i = trading days observed
    kappa_p        ~  N(1, TAU0^2)                        prior: the certificates are honest

kappa = 1 means live delivers what the gauntlet promised; kappa < 1 means the producer's priors
OVERSTATE live. The posterior updates every hour as the forward clocks and the live ledger grow.
The same arithmetic, pooled over every certificate, is the desk-wide live/backtest calibration.

THE LOOP IS CLOSED INTO RESEARCH CREDIT, LIVE. `credit_factor = clip(E[kappa_p], 0.5, 2.0)` is
published per producer and per bandit arm (`libs.research.bandit.arm_of`), and
`bandit.calibration_credit()` multiplies the arm's worth by it -- beside, never instead of, the
realised-R credit. With no evidence kappa's posterior mean IS the prior (1.0), so a producer with
no clocks is untouched; the factor moves only as far as the evidence moves the posterior. It
re-weights research-budget SHARES between arms (the allocator keeps its exploration floors); it
does not stop any producer. The CAPITAL side (downweighting a sleeve's heat by its producer's
kappa) is published per sleeve as `capital_factor_shadow` and FED NOWHERE: that is a sizing
change and NEEDS-PRINCIPAL-GO (`CAPITAL_SIDE_FEEDS_LIVE = False`, pinned by a test).

BESIDE THE EDGE, per sleeve and each with its own UNMEASURED: drawdown (realised max drawdown in
R against the distribution the certificate's own Sharpe implies over the same trade count),
slippage (entry fill against the intended price, in R, from the intent and live ledgers),
marginal contribution (the allocator's claimed dE[log W] against the realised R the sleeve's
heat earned), and correlation (realised pairwise correlation of daily live R against the
allocator's world population, where two sleeves share enough live days).

    python desks/mt5/research/live_calibration_posterior.py
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SHADOW = (DESK / "reports" / "shadow" / "shadow_state.json",
          DESK / "reports" / "shadow" / "qquant_shadow_state.json",
          DESK / "reports" / "shadow" / "scalp_shadow_state.json",
          DESK / "reports" / "shadow" / "external_shadow_state.json")
LEDGER = DESK / "data" / "live_ledger.jsonl"
INTENTS = DESK / "data" / "order_intents.jsonl"
SLEEVES = DESK / "data" / "sleeves.json"
ALLOCATION = DESK / "reports" / "pf_allocation.json"
WORLDS = DESK / "data" / "pf_allocator_cache" / "worlds.npz"
OUT = DESK / "reports" / "LIVE_CALIBRATION_POSTERIOR.json"

#: Prior sd on kappa. 0.5 says "a producer that delivers half of what it claims is a two-sigma
#: surprise before any evidence" -- honest-by-default, but movable by a few months of clocks.
TAU0 = 0.5
#: Live deals a sleeve needs before live replaces forward as its evidence.
MIN_LIVE_TRADES = 10
#: A certificate with fewer realised trades than this carries no calibration row (its Sharpe is
#: not an estimate yet); it is counted under `thin`.
MIN_TRADES = 5
CREDIT_CLIP = (0.5, 2.0)
#: The posterior probability of kappa < 1 above which a producer is flagged OVERSTATES.
OVERSTATE_P = 0.90
#: THE CAPITAL SIDE'S SWITCH. Off; see the module docstring.
CAPITAL_SIDE_FEEDS_LIVE = False
#: Monte Carlo draws for the drawdown distribution per sleeve.
DD_DRAWS = 2000


def _read(p: Path) -> Any:
    try:
        return json.loads(p.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return None


def _jsonl(p: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        text = p.read_text("utf-8", errors="replace")
    except OSError:
        return out
    for ln in text.splitlines():
        if not ln.strip():
            continue
        try:
            d = json.loads(ln)
        except ValueError:
            continue
        if isinstance(d, dict):
            out.append(d)
    return out


def _num(x: Any) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def claimed_sharpe(gates: dict[str, Any]) -> tuple[float | None, str]:
    """The certificate's own claim, per day: the most out-of-sample number it carries."""
    for gate, key in (("walk_forward", "oos_sharpe"), ("cpcv", "mean_oos_sharpe"),
                      ("lockbox", "lockbox_sharpe"), ("in_sample_screen", "sharpe")):
        v = _num((gates.get(gate) or {}).get(key)) if isinstance(gates.get(gate), dict) else None
        if v is not None:
            return v, f"{gate}.{key}"
    return None, "the certificate carries no Sharpe reading"


def posterior_kappa(rows: list[dict[str, Any]], tau0: float = TAU0) -> dict[str, Any]:
    """Conjugate Normal update of kappa from (s_i, e_i, N_i) rows. Pure."""
    prec = 1.0 / tau0 ** 2
    num = prec * 1.0
    used = 0
    for r in rows:
        e, s, n = _num(r.get("expected")), _num(r.get("realised")), _num(r.get("n_days"))
        if e is None or s is None or not n or n <= 0 or e <= 0:
            continue
        prec += n * e * e
        num += n * e * s
        used += 1
    mean = num / prec
    sd = 1.0 / math.sqrt(prec)
    p_over = 0.5 * (1.0 + math.erf((1.0 - mean) / (sd * math.sqrt(2.0))))
    return {"kappa_mean": round(mean, 4), "kappa_sd": round(sd, 4),
            "p_overstates": round(p_over, 4), "n_rows": used,
            "credit_factor": round(min(CREDIT_CLIP[1], max(CREDIT_CLIP[0], mean)), 4),
            "verdict": ("NO_EVIDENCE" if used == 0 else
                        "OVERSTATES" if p_over >= OVERSTATE_P else
                        "UNDERSTATES" if p_over <= 1.0 - OVERSTATE_P else "CALIBRATED")}


def per_certificate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One evidence row per certificate. Several forward clocks (bands, sessions) of ONE
    certificate run over the SAME days, so counting each as independent evidence would buy the
    posterior precision it does not have: realised is their day-weighted mean and N the longest
    window among them, never the sum."""
    acc: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        acc[str(r.get("certificate"))].append(r)
    out: list[dict[str, Any]] = []
    for cert, rs in acc.items():
        live = [r for r in rs if r.get("basis") == "live"]
        use = live or rs
        w = sum(float(r["n_days"]) for r in use)
        if w <= 0:
            continue
        out.append({"certificate": cert, "expected": use[0]["expected"],
                    "realised": sum(float(r["realised"]) * float(r["n_days"]) for r in use) / w,
                    "n_days": max(float(r["n_days"]) for r in use), "n_clocks": len(use)})
    return out


def _clock_rows() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for p in SHADOW:
        d = _read(p)
        if not isinstance(d, dict):
            continue
        for k, r in d.items():
            if isinstance(r, dict) and _num(r.get("n")) and _num(r.get("exp_r")) is not None:
                out[str(k)] = {**r, "lane_file": p.name}
    return out


def _forward_sharpe_per_day(r: dict[str, Any]) -> tuple[float | None, float, str]:
    """Realised Sharpe per trading day from a clock's (n, exp_r, forward_t, days_active)."""
    n = int(_num(r.get("n")) or 0)
    t = _num(r.get("forward_t"))
    days = _num(r.get("days_active"))
    if n < MIN_TRADES or t is None or not days or days <= 0:
        return None, 0.0, "forward clock lacks n / forward_t / days_active"
    per_trade = t / math.sqrt(n)
    trading_days = max(1.0, days * 5.0 / 7.0)
    f = n / trading_days
    # A day's R is the sum of ~f trades, so its mean is f * mu and its sd ~ sqrt(f) * sigma:
    # per-day Sharpe = per-trade Sharpe * sqrt(f), the scale the certificate's daily series used.
    return per_trade * math.sqrt(f), trading_days, "forward"


def _live_by_sleeve() -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for d in _jsonl(LEDGER):
        if _num(d.get("r_multiple")) is not None and d.get("sleeve"):
            out[str(d["sleeve"])].append(d)
    return out


def _live_sharpe_per_day(deals: list[dict[str, Any]]) -> tuple[float | None, float]:
    by_day: dict[str, float] = defaultdict(float)
    for d in deals:
        by_day[str(d.get("time") or "")[:10]] += float(d["r_multiple"])
    if len(deals) < MIN_LIVE_TRADES or len(by_day) < 3:
        return None, 0.0
    days = sorted(by_day)
    try:
        span = (datetime.fromisoformat(days[-1]) - datetime.fromisoformat(days[0])).days + 1
    except ValueError:
        span = len(days)
    trading_days = max(float(len(days)), span * 5.0 / 7.0)
    vals = [by_day.get(d, 0.0) for d in days] + [0.0] * max(0, int(trading_days) - len(days))
    m = sum(vals) / len(vals)
    var = sum((v - m) ** 2 for v in vals) / max(1, len(vals) - 1)
    if var <= 0:
        return None, 0.0
    return m / math.sqrt(var), trading_days


def expected_drawdown(sharpe_trade: float, n: int, draws: int = DD_DRAWS,
                      seed: int = 0) -> dict[str, float] | None:
    """Max drawdown (in per-trade sd units) over n trades at the claimed per-trade Sharpe."""
    if n < MIN_TRADES:
        return None
    import numpy as np
    rng = np.random.default_rng(seed)
    x = rng.standard_normal((draws, n)) + sharpe_trade
    cum = np.cumsum(x, axis=1)
    peak = np.maximum.accumulate(np.concatenate([np.zeros((draws, 1)), cum], axis=1), axis=1)
    dd = (peak[:, 1:] - cum).max(axis=1)
    return {"p50": float(np.median(dd)), "p90": float(np.quantile(dd, 0.9)),
            "samples": dd}  # type: ignore[dict-item]


def entry_slippage_r() -> dict[str, dict[str, Any]]:
    """Entry fill vs intended price, in R, per sleeve: the live half of the slippage question."""
    intents = {}
    for it in _jsonl(INTENTS):
        tk = it.get("ticket")
        if tk is not None:
            intents[str(tk)] = it
    acc: dict[str, list[float]] = defaultdict(list)
    for d in _jsonl(LEDGER):
        it = intents.get(str(d.get("entry_order"))) or intents.get(str(d.get("position_id")))
        if not it:
            continue
        want, got, sl = _num(it.get("intended")), _num(d.get("entry_price")), _num(it.get("sl"))
        if want is None or got is None or sl is None or abs(want - sl) <= 0:
            continue
        sign = 1.0 if str(it.get("side")).lower() in ("buy", "0") else -1.0
        acc[str(d.get("sleeve") or it.get("sleeve") or "")].append(
            sign * (got - want) / abs(want - sl))
    return {k: {"n": len(v), "mean_slip_r": round(sum(v) / len(v), 5)}
            for k, v in acc.items() if v and k}


def correlation_check(live: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """Realised pairwise corr of daily live R vs the allocator's worlds, per shared pair."""
    try:
        import numpy as np
        z = np.load(WORLDS, allow_pickle=False)
        names = [str(x) for x in z["names"]]
        r = np.asarray(z["r"], dtype=float)
    except Exception as exc:
        return {"status": "UNMEASURED", "why": f"no allocator world cache ({type(exc).__name__})"}
    flat = r.reshape(-1, r.shape[2])
    daily: dict[str, dict[str, float]] = {}
    for s, deals in live.items():
        if s in names:
            dd: dict[str, float] = defaultdict(float)
            for d in deals:
                dd[str(d.get("time") or "")[:10]] += float(d["r_multiple"])
            daily[s] = dd
    pairs = []
    keys = sorted(daily)
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            common = sorted(set(daily[a]) & set(daily[b]))
            if len(common) < 10:
                continue
            xa = np.array([daily[a][d] for d in common])
            xb = np.array([daily[b][d] for d in common])
            if xa.std() == 0 or xb.std() == 0:
                continue
            real = float(np.corrcoef(xa, xb)[0, 1])
            ia, ib = names.index(a), names.index(b)
            exp = float(np.corrcoef(flat[:, ia], flat[:, ib])[0, 1])
            pairs.append({"a": a, "b": b, "n_days": len(common), "realised": round(real, 4),
                          "expected": round(exp, 4), "gap": round(real - exp, 4)})
    if not pairs:
        return {"status": "UNMEASURED", "n_pairs": 0,
                "why": "no two worlds-priced sleeves share 10 live trading days yet"}
    return {"status": "MEASURED", "n_pairs": len(pairs),
            "mean_abs_gap": round(sum(abs(p["gap"]) for p in pairs) / len(pairs), 4),
            "worst": sorted(pairs, key=lambda p: -abs(p["gap"]))[:10]}


def build(now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    import credit_assignment as ca
    from libs.research.bandit import arm_of

    certs = ca.certificates()
    clocks = _clock_rows()
    fwd = [{"clock": k, "lane": r["lane_file"], "exp_r": float(r["exp_r"]), "n": int(r["n"]),
            "realised_r": float(r["exp_r"]) * int(r["n"]), "status": r.get("status"),
            "symbol": str(k).split(".")[0]} for k, r in clocks.items()]
    credited, unmatched = ca.match_forward(fwd, certs)
    live = _live_by_sleeve()
    live_rows = [{"sleeve": s, "symbol": str(d[0].get("symbol") or ""),
                  "realised_r": float(d[0]["r_multiple"])} for s, d in live.items()]
    live_credit = {r["clock"]: r for r in ca._credit_live(live_rows, certs)}
    by_cert = {c["certificate"]: c for c in certs}
    slip = entry_slippage_r()
    art = _read(ALLOCATION) if ALLOCATION.exists() else None
    marginal = (art.get("marginal_delta_elog") or {}) if isinstance(art, dict) else {}
    doc_sl = _read(SLEEVES)
    sl_rows = doc_sl.get("sleeves") if isinstance(doc_sl, dict) else doc_sl
    risk_frac = {str(r.get("name")): _num(r.get("risk_frac")) or 0.0 for r in sl_rows or []
                 if isinstance(r, dict) and r.get("name")}

    sleeves: list[dict[str, Any]] = []
    thin = 0
    # Forward-evidenced certificates.
    for c in credited:
        cert = by_cert.get(c["certificate"]) or {}
        e, e_basis = claimed_sharpe(cert.get("gates") or {})
        r = clocks.get(c["clock"]) or {}
        s, n_days, basis = _forward_sharpe_per_day(r)
        if s is None or e is None:
            thin += 1
            continue
        n = int(r.get("n") or 0)
        f = n / n_days if n_days else 0.0
        row: dict[str, Any] = {
            "sleeve": c["clock"], "certificate": c["certificate"], "producer": c["source"],
            "arm": arm_of(c["source"]), "basis": basis, "n_trades": n,
            "n_days": round(n_days, 1), "expected": round(e, 5), "expected_basis": e_basis,
            "realised": round(s, 5), "ratio": round(s / e, 4) if e > 0 else None}
        dd_real = _num(r.get("max_dd_r"))
        sd_trade = (abs(float(r["exp_r"])) * math.sqrt(n) / abs(float(r["forward_t"]))
                    if _num(r.get("forward_t")) else None)
        if dd_real is not None and sd_trade and f > 0:
            exp_trade = e / math.sqrt(f) if f > 0 else e
            ed = expected_drawdown(exp_trade, n)
            if ed is not None:
                real_units = abs(dd_real) / sd_trade
                samples = ed.pop("samples")
                row["drawdown"] = {"realised_r": round(dd_real, 4),
                                   "realised_sd_units": round(real_units, 3),
                                   "expected_p50_sd_units": round(ed["p50"], 3),
                                   "expected_p90_sd_units": round(ed["p90"], 3),
                                   "p_as_bad": round(float((samples >= real_units).mean()), 4)}
        sleeves.append(row)
    # Live-evidenced sleeves replace forward when thick enough.
    for sname, deals in live.items():
        lc = live_credit.get(sname)
        if not lc:
            continue
        s, n_days = _live_sharpe_per_day(deals)
        cert = by_cert.get(lc["certificate"]) or {}
        e, e_basis = claimed_sharpe(cert.get("gates") or {})
        if s is None or e is None:
            continue
        sleeves = [x for x in sleeves if x["certificate"] != lc["certificate"]
                   or x["basis"] == "live"]
        realised_contrib = sum(float(d["r_multiple"]) for d in deals) * risk_frac.get(sname, 0.0)
        sleeves.append({
            "sleeve": sname, "certificate": lc["certificate"], "producer": lc["source"],
            "arm": arm_of(lc["source"]), "basis": "live", "n_trades": len(deals),
            "n_days": round(n_days, 1), "expected": round(e, 5), "expected_basis": e_basis,
            "realised": round(s, 5), "ratio": round(s / e, 4) if e > 0 else None,
            "marginal_contribution": {
                "expected_marginal_delta_elog": _num(marginal.get(sname)),
                "realised_log_contribution_per_day": (round(realised_contrib / n_days, 6)
                                                      if n_days else None),
                "risk_frac": risk_frac.get(sname)}})
    for row in sleeves:
        if row["sleeve"] in slip:
            row["slippage"] = {**slip[row["sleeve"]], "expected_slip_r": 0.0,
                               "expected_basis": "the certificate charged modelled spread; any "
                                                 "entry slip beyond the intended price is unpriced"}
        else:
            row.setdefault("slippage", {"status": "UNMEASURED",
                                        "why": "no intent joined to a live fill for this sleeve"})
        if "marginal_contribution" not in row:
            row["marginal_contribution"] = {
                "expected_marginal_delta_elog": _num(marginal.get(row["sleeve"])),
                "realised_log_contribution_per_day": None,
                "why": "forward evidence only: no live heat has earned anything yet"}

    by_producer: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in sleeves:
        by_producer[row["producer"]].append(row)
    producers = {p: {**posterior_kappa(per_certificate(rows)), "arm": arm_of(p),
                     "n_live": sum(1 for r in rows if r["basis"] == "live")}
                 for p, rows in sorted(by_producer.items())}
    by_arm_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in sleeves:
        by_arm_rows[row["arm"]].append(row)
    arms = {a: posterior_kappa(per_certificate(rows)) for a, rows in sorted(by_arm_rows.items())}
    pooled = posterior_kappa(per_certificate(sleeves))
    for row in sleeves:
        k = producers.get(row["producer"], {}).get("credit_factor", 1.0)
        row["capital_factor_shadow"] = k
    return {
        "at": now.isoformat(timespec="seconds"),
        "status": "MEASURED" if sleeves else "UNMEASURED",
        "why": (f"{len(sleeves)} certificate(s) with realised evidence; {thin} too thin; "
                f"{unmatched} forward clock(s) not traceable to a certificate"
                if sleeves else "no certificate has enough realised evidence yet"),
        "model": {"likelihood": "s_i ~ N(kappa * e_i, 1/N_i), N_i trading days observed",
                  "prior": f"kappa ~ N(1, {TAU0}^2): the certificates are honest until shown not",
                  "credit_factor": f"clip(E[kappa], {CREDIT_CLIP[0]}, {CREDIT_CLIP[1]})",
                  "overstates_when": f"P(kappa < 1) >= {OVERSTATE_P}"},
        "pooled": pooled,
        "by_producer": producers,
        "by_arm": arms,
        "credit": {"applied_to": "libs/research/bandit.calibration_credit -> arm worth "
                                 "(research budget shares); live",
                   "by_arm": {a: v["credit_factor"] for a, v in arms.items()
                              if v["n_rows"] > 0}},
        "capital_side": {"feeds_live": CAPITAL_SIDE_FEEDS_LIVE,
                         "why": ("downweighting a sleeve's HEAT by its producer's kappa is a "
                                 "sizing change: published per sleeve as capital_factor_shadow, "
                                 "fed nowhere -- NEEDS-PRINCIPAL-GO")},
        "correlation": correlation_check(live),
        "sleeves": sorted(sleeves, key=lambda r: (r["producer"], r["sleeve"])),
        "n_thin": thin,
        "n_unmatched_clocks": unmatched,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    doc = build()
    if not args.dry_run:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(doc, indent=2, default=str), "utf-8")
    p = doc["pooled"]
    print(f"live_calibration_posterior: {doc['status']} -- pooled kappa {p['kappa_mean']} "
          f"+/- {p['kappa_sd']} over {p['n_rows']} row(s); "
          f"{sum(1 for v in doc['by_producer'].values() if v['verdict'] == 'OVERSTATES')} "
          f"producer(s) overstate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
