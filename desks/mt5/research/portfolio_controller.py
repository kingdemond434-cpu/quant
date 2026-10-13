"""PORTFOLIO CONTROLLER, PHASE 1: the online edge monitor (2026-10-13).

THE QUESTION THAT CREATED IT. AUDCHF overnight_gap_decay lost -1.02R live on 2026-10-13 at the
10% risk-per-trade the CERT_BOOK_LIVE overlay pins. The principal asked why the allocator did not
see the trade going against it and dynamically re-size, like a human watching the book. The
answer had two parts. First, the CERT_BOOK overlay is a STATIC fraction laid over the allocator's
answer, so no amount of evidence moved it. Second, the existing decay machinery reads
FADE / RETIRE only at n >= 20 (`decay_monitor`), and the allocator's per-sleeve `decay_prob_i`
came only from the drift monitor's hazard. Nothing updated a sleeve's edge trade by trade.

WHAT THIS DOES EACH CYCLE (a few-minute cadence on the box, plus an hourly leg):

  1. EDGE POSTERIOR per sleeve. Normal-normal conjugate on mean R per trade:
       prior    = certificate's in-sample mean, SHRUNK by CERT_SHRINK toward zero, sd PRIOR_SD_R
       evidence = forward-clock trades + live trades, DE-DUPLICATED: a live fill and its forward
                  clock row are the same signal on the same day, so the forward count used is
                  max(0, n_forward - n_live) at the forward mean (live preferred, never both).
     Published: posterior mean, sd, P(edge <= 0).
  2. DECAY ALARM. A one-sided Page CUSUM and a Wald SPRT on the live sequence, prior mean versus
     DECAY_MU1_R. States: OK / WATCH / ALARM, with the statistic and its bar.
  3. FRACTION. The posterior E[log W]-optimal risk per trade for an R-outcome bet, with the
     parameter uncertainty counted in the variance: f* = mu / (sigma^2 + sd_post^2), clipped to
     [0, sizing.MAX_RISK_FRAC], and the book scaled into the 30% heat ceiling. TWO-SIDED: as
     evidence improves, mu rises and sd falls, so the fraction RISES (GROWTH_GOVERNANCE Rule 2).
     A sleeve on the minimum-lot override allowlist (`data/MINLOT_OVERRIDE.json`, specced in
     patches/auto_survival_heat) is reported `override_pinned`; the controller never lowers it.
  4. HAND-OFF. `hazard_by_sleeve` = P(edge <= 0) per sleeve alias. `pf_allocator` reads it
     beside the drift monitor's hazard and writes it onto each sleeve's `decay_prob_i`, the
     existing evidence path (capped at the blanket by `robust_elog.decay_prob_of`, billed by
     `missed_growth.measure_decay_posterior`). The gateway reading `fraction` directly, and the
     CERT_BOOK overlay ceasing to override it, are money-path and are a laptop spec
     (patches/portfolio_controller/README.md); this module never sends or sizes an order.
  5. LATER-PHASE HOOKS. Position-manager survivors, Fusion+E8 netting / opposite-side guards,
     spread and session from the cost surface, regime state. Each reports what it read; an
     absent input is UNMEASURED with the reason, never a zero and never a pass.
  6. DECISIONS. Every change of a sleeve's fraction or alarm state is appended with its reason to
     `data/controller_decisions.jsonl`.
  7. VALUE-ADD. A causal replay over the recorded live sequence: the fraction the controller
     would have held BEFORE each trade, times that trade's R, against the static book's
     fraction. Per sleeve and in total, both signs: R saved and growth missed.

Artifact: reports/EDGE_MONITOR.json.
"""
from __future__ import annotations

import json
import math
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
DATA = BASE / "data"
REPORTS = BASE / "reports"
OUT = REPORTS / "EDGE_MONITOR.json"
DECISIONS = DATA / "controller_decisions.jsonl"
STATE = DATA / "controller_state.json"
LIVE_LEDGER = DATA / "live_ledger.jsonl"
SHADOW_STATE = REPORTS / "shadow" / "shadow_state.json"
CERT_BOOK = DATA / "CERT_BOOK_LIVE.json"
SLEEVES = DATA / "sleeves.json"
MINLOT_OVERRIDE = DATA / "MINLOT_OVERRIDE.json"
COST_SURFACE = DATA / "cost_surface.json"
SHADOW_LEDGER_DIRS = (REPORTS / "shadow", ROOT / "backups" / "moat" / "shadow_ledgers")
SIZING = BASE / "mt5desk" / "sizing.py"

#: The certificate's in-sample mean is a claim made on the data that selected it; half of it is
#: what the prior believes. Selection bias on a ten-gate survivor is of this order.
CERT_SHRINK = 0.5
#: Prior sd on mean R: wide enough that ~16 trades weigh as much as the certificate.
PRIOR_SD_R = 0.25
#: The desk prior when a sleeve's certificate carries no in-sample series: a modest positive edge.
DEFAULT_PRIOR_R = 0.10
#: Per-trade R noise floor; the pooled live sd is used when it is larger and measured.
SIGMA_FLOOR_R = 0.8
MIN_POOL_FOR_SIGMA = 20
#: Decay hypothesis for CUSUM / SPRT: the edge has turned to this mean R.
DECAY_MU1_R = -0.25
CUSUM_H = 4.0
CUSUM_WATCH = 2.0
SPRT_ALPHA = 0.05
SPRT_BETA = 0.20
HEAT_CEILING = 0.30
DEFAULT_MAX_RISK_FRAC = 0.10
LEDGER_NAME_MAX = 27
#: Clock aliases a book key cannot be derived to by normalisation alone.
CLOCK_ALIASES = {"gold_asia": "xauusd_asia"}


# ---------------------------------------------------------------------------------- helpers

def _read_json(p: Path, default: Any) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def norm(name: str) -> str:
    """One spelling for a sleeve across book key, clock key and ledger comment."""
    s = str(name).split("#", 1)[0].lower().replace(".", "_")
    s = re.sub(r"_p_[0-9a-f]{8,}$", "", s)
    return s


def stem(name: str) -> str:
    return norm(name)[:LEDGER_NAME_MAX]


def max_risk_frac(path: Path = SIZING) -> float:
    """sizing.MAX_RISK_FRAC read as text (importing sizing pulls in the terminal bindings)."""
    try:
        m = re.search(r"^MAX_RISK_FRAC\s*=\s*([0-9.]+)", path.read_text("utf-8"), re.M)
        if m:
            return float(m.group(1))
    except OSError:
        pass
    return DEFAULT_MAX_RISK_FRAC


def _phi(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


# ---------------------------------------------------------------------------------- inputs

def live_trades(path: Path = LIVE_LEDGER) -> dict[str, list[tuple[str, float]]]:
    """{ledger stem: [(time, R), ...]} oldest first, live account rows with a MEASURED R only."""
    out: dict[str, list[tuple[str, float]]] = {}
    try:
        lines = path.read_text("utf-8").splitlines()
    except OSError:
        return out
    for line in lines:
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if not isinstance(r, dict) or r.get("r_unreconstructible") is True:
            continue
        rv = r.get("r_multiple")
        rq = r.get("risk_quote")
        if not isinstance(rv, (int, float)) or isinstance(rv, bool):
            continue
        if isinstance(rq, (int, float)) and rq <= 0:
            continue                                   # unmeasured R written as 0.0
        if r.get("account_kind") not in (None, "live"):
            continue
        out.setdefault(stem(str(r.get("sleeve", ""))), []).append((str(r.get("time", "")),
                                                                  float(rv)))
    for v in out.values():
        v.sort(key=lambda p: p[0])
    return out


def forward_clocks(path: Path = SHADOW_STATE) -> dict[str, dict[str, Any]]:
    """{norm(clock): {"n", "mean"}} forward-phase aggregates; the bare clock wins over variants."""
    doc = _read_json(path, {})
    out: dict[str, dict[str, Any]] = {}
    if not isinstance(doc, dict):
        return out
    for key, row in sorted(doc.items(), key=lambda kv: "#" in kv[0]):
        if not isinstance(row, dict):
            continue
        n, m = row.get("n"), row.get("exp_r")
        if not isinstance(n, int) or not isinstance(m, (int, float)) or n <= 0:
            continue
        k = norm(key)
        if k in out:
            continue                    # bare keys sort first: the registered clock wins
        out[k] = {"n": float(n), "mean": float(m),
                  "first": str(row.get("first_entry") or ""),
                  "last": str(row.get("last_entry") or "")}
    return out


def cert_prior_mean(clock: str) -> tuple[float, str]:
    """In-sample (historical-phase) mean R from the sleeve's clock ledger, else the desk prior."""
    fname = f"ledger_{norm(clock)}.json"
    for d in SHADOW_LEDGER_DIRS:
        try:
            hit = next((f for f in d.iterdir() if f.name.lower() == fname), None)
        except OSError:
            hit = None
        rows = _read_json(hit, None) if hit is not None else None
        if not isinstance(rows, list):
            continue
        hist = [float(r["r_multiple"]) for r in rows if isinstance(r, dict)
                and r.get("phase") == "historical"
                and isinstance(r.get("r_multiple"), (int, float))]
        if len(hist) >= 3:
            return sum(hist) / len(hist), f"{d.name}/{fname} historical n={len(hist)}"
    return DEFAULT_PRIOR_R / CERT_SHRINK, "desk default (no in-sample series found)"


def book() -> dict[str, float]:
    """The static book the controller is measured against: CERT_BOOK_LIVE fusion fractions."""
    doc = _read_json(CERT_BOOK, {})
    if not isinstance(doc, dict) or not doc.get("enabled"):
        return {}
    fus = doc.get("fusion") or {}
    return {str(k): float(v) for k, v in fus.items() if isinstance(v, (int, float))}


def override_allowlist(path: Path = MINLOT_OVERRIDE) -> tuple[set[str], str]:
    doc = _read_json(path, None)
    if not isinstance(doc, dict):
        return set(), f"UNMEASURED: {path.name} absent (specced in patches/auto_survival_heat)"
    if not doc.get("enabled"):
        return set(), f"{path.name} disabled"
    names = {norm(s.get("name", "")) for s in doc.get("sleeves") or [] if isinstance(s, dict)}
    return names, f"{len(names)} sleeve(s) on the minimum-lot override allowlist"


# ---------------------------------------------------------------------------------- the model

def posterior(prior_mean: float, fwd_n: float, fwd_mean: float, live: list[float],
              sigma: float, prior_sd: float = PRIOR_SD_R) -> dict[str, Any]:
    """Normal-normal posterior on mean R, forward count de-duplicated against live fills."""
    n_live = len(live)
    fwd_eff = max(0.0, fwd_n - n_live)
    prec = 1.0 / prior_sd ** 2 + (fwd_eff + n_live) / sigma ** 2
    num = prior_mean / prior_sd ** 2 + (fwd_eff * fwd_mean + sum(live)) / sigma ** 2
    mu = num / prec
    sd = math.sqrt(1.0 / prec)
    return {"mean_r": mu, "sd_r": sd, "p_edge_le_0": _phi(-mu / sd),
            "n_live": n_live, "n_forward_used": fwd_eff, "n_forward_raw": fwd_n,
            "prior_mean_r": prior_mean}


def kelly_fraction(mu: float, sd_post: float, sigma: float, cap: float) -> float:
    """E[log W]-optimal risk per trade for an R bet, parameter uncertainty in the variance."""
    if mu <= 0:
        return 0.0
    return min(cap, mu / (sigma ** 2 + sd_post ** 2))


def decay_alarm(prior_mean: float, live: list[float], sigma: float) -> dict[str, Any]:
    """Page CUSUM (downward) and Wald SPRT, prior mean versus DECAY_MU1_R."""
    k = (prior_mean + DECAY_MU1_R) / 2.0
    s, smax, llr = 0.0, 0.0, 0.0
    a = math.log((1 - SPRT_BETA) / SPRT_ALPHA)
    b = math.log(SPRT_BETA / (1 - SPRT_ALPHA))
    sprt = "CONTINUE"
    for x in live:
        s = max(0.0, s + (k - x) / sigma)
        smax = max(smax, s)
        llr += (DECAY_MU1_R - prior_mean) * (x - k) / sigma ** 2
        if llr >= a:
            sprt = "DECAY"
        elif llr <= b:
            sprt, llr = "HEALTHY", 0.0
    state = "ALARM" if (s >= CUSUM_H or sprt == "DECAY") else (
        "WATCH" if s >= CUSUM_WATCH else "OK")
    if not live:
        state = "UNMEASURED"
    return {"state": state, "cusum": round(s, 4), "cusum_h": CUSUM_H, "sprt_llr": round(llr, 4),
            "sprt_bounds": [round(b, 4), round(a, 4)], "sprt": sprt, "n": len(live)}


def pooled_sigma(trades: dict[str, list[tuple[str, float]]]) -> tuple[float, str]:
    xs = [r for v in trades.values() for _, r in v]
    if len(xs) < MIN_POOL_FOR_SIGMA:
        return SIGMA_FLOOR_R, f"floor (pooled n={len(xs)} < {MIN_POOL_FOR_SIGMA})"
    m = sum(xs) / len(xs)
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))
    return max(SIGMA_FLOOR_R, sd), f"pooled live sd {sd:.3f} over n={len(xs)}"


def _ts(s: str) -> float | None:
    try:
        t = datetime.fromisoformat(s.replace("Z", "+00:00").replace(" ", "T"))
    except ValueError:
        return None
    return (t if t.tzinfo else t.replace(tzinfo=UTC)).timestamp()


def forward_n_by(fwd: dict[str, Any], at: str) -> float:
    """Forward trades the clock had closed by `at`, PRORATED evenly between its first and last
    entry: shadow_state keeps the aggregate, not per-trade times. APPROXIMATE, and labelled so."""
    n = float(fwd.get("n") or 0.0)
    t0, t1, t = _ts(str(fwd.get("first", ""))), _ts(str(fwd.get("last", ""))), _ts(at)
    if not n or t0 is None or t1 is None or t is None or t < t0:
        return 0.0
    if t >= t1 or t1 <= t0:
        return n
    return math.floor(1 + (n - 1) * (t - t0) / (t1 - t0))


def replay(prior_mean: float, fwd: dict[str, Any], seq: list[tuple[str, float]],
           sigma: float, cap: float, static_frac: float) -> dict[str, Any]:
    """Causal: the fraction held BEFORE each live trade, from the prior, the forward trades the
    clock had closed by then (prorated, see `forward_n_by`) and earlier live trades only."""
    rows = []
    ctrl = stat = 0.0
    first_cut = None
    for i, (ts, r) in enumerate(seq):
        past = [x for _, x in seq[:i]]
        p = posterior(prior_mean, forward_n_by(fwd, ts), float(fwd.get("mean") or 0.0),
                      past, sigma)
        f = kelly_fraction(p["mean_r"], p["sd_r"], sigma, cap)
        ctrl += f * r
        stat += static_frac * r
        if first_cut is None and f < static_frac - 1e-9:
            first_cut = {"before_trade_at": ts, "fraction": round(f, 4),
                         "static": static_frac}
        rows.append({"time": ts, "r": round(r, 4), "fraction": round(f, 4),
                     "posterior_mean_r": round(p["mean_r"], 4),
                     "n_forward_used": p["n_forward_used"]})
    return {"trades": rows, "controller_equity_r": round(ctrl, 5),
            "static_equity_r": round(stat, 5), "value_add": round(ctrl - stat, 5),
            "first_cut": first_cut, "static_fraction": static_frac,
            "unit": "sum(fraction x R): fraction-of-equity, pre-compounding",
            "forward_timing": "APPROXIMATE: forward trades prorated between first/last entry"}


def cut_timeline(prior_mean: float, fwd: dict[str, Any], seq: list[tuple[str, float]],
                 sigma: float, cap: float, static_frac: float, now: datetime) -> dict[str, Any]:
    """Day by day from the clock's first forward entry: the first day the controller would hold
    less than the static book, and the first day it would hold nothing (both APPROXIMATE)."""
    t0 = _ts(str(fwd.get("first", "")))
    out: dict[str, Any] = {"first_below_static": None, "first_zero": None}
    if t0 is None:
        return out
    day, end = t0, now.timestamp()
    while day <= end:
        at = datetime.fromtimestamp(day, tz=UTC).isoformat()
        live = [r for ts, r in seq if (_ts(ts) or 0.0) <= day]
        p = posterior(prior_mean, forward_n_by(fwd, at), float(fwd.get("mean") or 0.0),
                      live, sigma)
        f = kelly_fraction(p["mean_r"], p["sd_r"], sigma, cap)
        if out["first_below_static"] is None and f < static_frac - 1e-9:
            out["first_below_static"] = {"date": at[:10], "fraction": round(f, 4)}
        if out["first_zero"] is None and f <= 0.0:
            out["first_zero"] = {"date": at[:10], "posterior_mean_r": round(p["mean_r"], 4)}
            break
        day += 86400.0
    return out


# ---------------------------------------------------------------------------------- hooks

def _hook_file(name: str, path: Path, why: str) -> dict[str, Any]:
    if not path.exists():
        return {"hook": name, "status": "UNMEASURED", "why": f"{path.name} absent: {why}"}
    try:
        age_h = (datetime.now(tz=UTC).timestamp() - path.stat().st_mtime) / 3600.0
    except OSError:
        age_h = None
    return {"hook": name, "status": "READ_NOT_ACTED", "source": str(path.relative_to(ROOT)),
            "age_h": None if age_h is None else round(age_h, 2),
            "why": f"input present; phase-1 controller publishes it and acts on nothing. {why}"}


def hooks() -> list[dict[str, Any]]:
    return [
        _hook_file("position_manager_survivors", REPORTS / "POSITION_MANAGER.json",
                   "later phase: in-trade management survivors"),
        {"hook": "netting_opposite_side_guards", "status": "UNMEASURED",
         "why": "Fusion+E8 netting and opposite-side guards are a later phase; no input read"},
        _hook_file("spread_session_cost_surface", COST_SURFACE,
                   "later phase: spread and session awareness"),
        _hook_file("regime_state", REPORTS / "DRIFT.json", "later phase: regime state"),
    ]


# ---------------------------------------------------------------------------------- the cycle

def _universe(bk: dict[str, float], trades: dict[str, Any]) -> dict[str, str]:
    """{norm(name): display name}: the static book plus every live-ledger sleeve."""
    names = {norm(k): k for k in bk}
    known_stems = {stem(k) for k in bk}
    for s in trades:
        if s and s not in known_stems:
            names.setdefault(s, s)
    return names


def run(now: datetime | None = None, write: bool = True) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    bk = book()
    trades = live_trades()
    fwd = forward_clocks()
    sigma, sigma_why = pooled_sigma(trades)
    cap = max_risk_frac()
    pinned, pinned_why = override_allowlist()
    sleeves: dict[str, Any] = {}
    for key, disp in sorted(_universe(bk, trades).items()):
        clock = CLOCK_ALIASES.get(key, key)
        f: dict[str, Any] = fwd.get(clock) or {"n": 0.0, "mean": 0.0, "first": "", "last": ""}
        cert_mean, prior_src = cert_prior_mean(clock)
        prior = CERT_SHRINK * cert_mean
        seq = trades.get(stem(key), [])
        live = [r for _, r in seq]
        p = posterior(prior, float(f["n"]), float(f["mean"]), live, sigma)
        static = bk.get(disp)
        on_book = static is not None
        frac = kelly_fraction(p["mean_r"], p["sd_r"], sigma, cap) if on_book else 0.0
        sleeves[disp] = {
            "posterior": {k: (round(v, 5) if isinstance(v, float) else v) for k, v in p.items()},
            "prior_source": prior_src,
            "alarm": decay_alarm(prior, live, sigma),
            "on_book": on_book,
            "fraction_raw": round(frac, 5),
            "static_fraction": static,
            "override_pinned": key in pinned,
            "aliases": sorted({disp, key, stem(key), clock}),
            # value-add is measured only where the static book names a fraction: a sleeve off
            # the book has no static counterpart to beat, and inventing one would be a claim.
            "replay": replay(prior, f, seq, sigma, cap, static)
            if (seq and static is not None) else None,
            "cut_timeline": cut_timeline(prior, f, seq, sigma, cap, static, now)
            if static is not None else None,
        }
    tot = sum(s["fraction_raw"] for s in sleeves.values())
    scale = HEAT_CEILING / tot if tot > HEAT_CEILING else 1.0
    for s in sleeves.values():
        if not s["on_book"]:
            s["fraction"] = None       # monitored only: not on the static book the gateway trades
            continue
        s["fraction"] = round(s["fraction_raw"] * scale, 5)
        if s["override_pinned"] and s["static_fraction"] is not None:
            s["fraction"] = max(s["fraction"], float(s["static_fraction"]))
    hazard = {a: round(s["posterior"]["p_edge_le_0"], 5)
              for s in sleeves.values() for a in s["aliases"]}
    reps = [s["replay"] for s in sleeves.values() if s["replay"]]
    doc = {
        "generated_utc": now.isoformat(), "phase": 1, "module": "research/portfolio_controller.py",
        "model": {"prior": f"certificate in-sample mean x {CERT_SHRINK}, sd {PRIOR_SD_R}R",
                  "sigma_r": round(sigma, 4), "sigma_source": sigma_why,
                  "dedup": "forward n used = max(0, n_forward - n_live)",
                  "fraction": "mu / (sigma^2 + sd_post^2), clip [0, MAX_RISK_FRAC], book <= 30%",
                  "max_risk_frac": cap, "heat_ceiling": HEAT_CEILING,
                  "heat_scale": round(scale, 5),
                  "alarm": f"CUSUM h={CUSUM_H} / SPRT a={SPRT_ALPHA} b={SPRT_BETA} "
                           f"vs mu1={DECAY_MU1_R}R"},
        "override_allowlist": pinned_why,
        "sleeves": sleeves,
        "hazard_by_sleeve": hazard,
        "hooks": hooks(),
        "value_add_vs_static": {
            "controller_equity_r": round(sum(r["controller_equity_r"] for r in reps), 5),
            "static_equity_r": round(sum(r["static_equity_r"] for r in reps), 5),
            "value_add": round(sum(r["value_add"] for r in reps), 5),
            "r_saved": round(sum(r["value_add"] for r in reps if r["value_add"] > 0), 5),
            "growth_missed": round(-sum(r["value_add"] for r in reps if r["value_add"] < 0), 5),
            "n_sleeves": len(reps),
            "basis": "causal replay on the recorded live ledger (missed-growth line: "
                     "growth_missed is what the controller gave up where it was smaller)"},
        "consumers": ["research/pf_allocator.py (decay_prob_i via hazard_by_sleeve)",
                      "gateway fraction: laptop spec patches/portfolio_controller/README.md"],
    }
    if write:
        REPORTS.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(doc, indent=1, sort_keys=True), "utf-8")
        log_decisions(doc, now)
    return doc


def log_decisions(doc: dict[str, Any], now: datetime,
                  state_path: Path = STATE, log_path: Path = DECISIONS) -> int:
    """Append one row per sleeve whose fraction or alarm changed since the last cycle."""
    prev = _read_json(state_path, {})
    prev = prev if isinstance(prev, dict) else {}
    cur, rows = {}, []
    for name, s in doc["sleeves"].items():
        sig = {"fraction": s["fraction"], "alarm": s["alarm"]["state"]}
        cur[name] = sig
        if prev.get(name) == sig:
            continue
        p = s["posterior"]
        rows.append({"at": now.isoformat(), "sleeve": name, "from": prev.get(name), "to": sig,
                     "static_fraction": s["static_fraction"],
                     "reason": (f"posterior mean {p['mean_r']:+.3f}R sd {p['sd_r']:.3f} "
                                f"P(edge<=0)={p['p_edge_le_0']:.2f} on n_live={p['n_live']} "
                                f"n_fwd={p['n_forward_used']:.0f}; alarm "
                                f"{s['alarm']['state']} (cusum {s['alarm']['cusum']})"
                                + ("; override-pinned" if s["override_pinned"] else ""))})
    if rows:
        with log_path.open("a", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, sort_keys=True) + "\n")
    state_path.write_text(json.dumps(cur, indent=1, sort_keys=True), "utf-8")
    return len(rows)


def hazard_for(names: list[str], path: Path = OUT, max_age_h: float = 2.0) -> dict[str, float]:
    """P(edge <= 0) for each allocator sleeve name the monitor knows; {} when stale or absent."""
    doc = _read_json(path, None)
    if not isinstance(doc, dict):
        return {}
    try:
        gen = datetime.fromisoformat(str(doc.get("generated_utc")))
        if (datetime.now(tz=UTC) - gen).total_seconds() > max_age_h * 3600:
            return {}
    except (TypeError, ValueError):
        return {}
    hz = doc.get("hazard_by_sleeve") or {}
    out = {}
    for n in names:
        for k in (n, norm(n), stem(n)):
            v = hz.get(k)
            if isinstance(v, (int, float)) and 0.0 < float(v) <= 1.0:
                out[n] = float(v)
                break
    return out


def main() -> int:
    doc = run()
    va = doc["value_add_vs_static"]
    print(f"[portfolio_controller] {len(doc['sleeves'])} sleeve(s); value-add vs static "
          f"{va['value_add']:+.4f} (saved {va['r_saved']:.4f}, missed {va['growth_missed']:.4f})")
    for n, s in doc["sleeves"].items():
        if not s["on_book"]:
            continue
        p = s["posterior"]
        print(f"  {n}: mu={p['mean_r']:+.3f} sd={p['sd_r']:.3f} P<=0={p['p_edge_le_0']:.2f} "
              f"alarm={s['alarm']['state']} f={s['fraction']:.4f} static={s['static_fraction']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
