"""Does the posterior-sized book grow capital faster than one static size per sleeve? REPORT ONLY.

    python research/posterior_sizing_missed_growth.py

The Auditor's measurement. The desk's main sizing already turns evidence into a per-sleeve
fraction through a Bayesian posterior (`libs/portfolio/robust_elog._posterior_mu`: n/(n+k)
shrinkage sleeve -> family -> asset class -> no edge, then the session-state level and the macro
regime contrast) and a regime mix over the sampled worlds (`pf_allocator.regime_state` ->
`WorldConfig.regime_probs`). Nobody had measured, on the desk's OWN realised trade streams,
whether that moving fraction earned more log wealth than a fraction that never moved. This does,
walk-forward and out of sample, per (account, sleeve) stream, and publishes the difference as a
signed missed-growth line so the modifier is two-sided on the ledger (GROWTH_GOVERNANCE Rule 1).

BOOK A, "as sized" -- two bases, each published, the first that is measured is the headline:

  recorded  the fraction actually attached to the trade. In order of preference: a fraction on
            the ledger row itself (`risk_fraction`/`risk_frac`, or `risk_usd` with `equity`);
            else the allocator-book fraction `portfolio_context.h` the gateway stamped on the
            EXECUTED decision row (`data/decision_ledger.jsonl`), joined by broker ticket
            (decision `ticket` == ledger `entry_order` / `position_id` / `order`). `h` is the
            TARGET the allocator posted, decided before the trade's outcome existed; the venue
            lot step may have snapped the order away from it, and the ledger carries no equity
            to recover the filled fraction from (`risk_quote` alone is not a fraction).
  replay    where nothing was recorded: the LIVE solve (`robust_elog.optimise`, which samples
            its worlds through `_posterior_mu`) re-run on the stream's own trades 1..t and
            applied to trade t+1. Called, not re-implemented. It is the single-sleeve posterior
            only: per-trade R stands in for daily R, and the family, asset-class, session-state
            and macro levels have nothing to pool with on a lone stream.

BOOK B, static -- both published, `static_first` is the headline baseline:

  static_first      the sleeve's FIRST posted fraction of book A, held for every later trade.
                    The fairer baseline: same scale and same information as the first post, so
                    the delta is exactly what the later evidence-driven resizing earned or cost.
  static_expanding  the plain growth-optimal fraction (grid argmax of mean log(1 + f r)) on
                    trades 1..t. No posterior, no look-ahead; it is NOT scale-matched to the
                    recorded fractions, so its delta mixes leverage level with timing.

Every fraction applied to trade t+1 is a function of trades 1..t only (and, for `recorded`, of a
decision stamped before the fill). Absent input is UNMEASURED with a why, never zero.

AUTHORITY: NONE. Reads two ledgers and the forward shadow ledgers, writes one report. Nothing
here touches the gateway, decision_core, the allocator's output, the promoter, rails or any
signed file; no trading entry point imports it.
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import numpy as np

from libs.ops.live_ledger_view import ledger_path
from libs.ops.win_write import write_text_resilient
from libs.portfolio.robust_elog import SleeveEvidence, WorldConfig, optimise

DESK = Path(__file__).resolve().parent.parent
LEDGER = DESK / "data" / "live_ledger.jsonl"
DECISIONS = DESK / "data" / "decision_ledger.jsonl"
SHADOW_DIR = DESK / "reports" / "shadow"
OUT = DESK / "reports" / "posterior_sizing_missed_growth.json"

SCHEMA = "posterior_sizing_missed_growth/1"
UNMEASURED = "UNMEASURED"
MEASURED = "MEASURED"
EARNS, COSTS = "EARNS_ITS_PLACE", "COSTS_GROWTH"
#: A measured delta whose pooled t-stat does not clear SIGNIFICANT_T (or has none). NOT_BINDING
#: would be wrong here: that word means a rail did not fire, and this book did trade.
NOT_SIGNIFICANT = "NOT_SIGNIFICANT"
#: |t| the pooled per-trade differences must reach before the sign of the summed delta is
#: published as a gain or a cost. `missed_growth.POSTERIOR_SIZING_SIGNIFICANT_T` is the same
#: number and a test pins the two together.
SIGNIFICANT_T = 2.0

#: THE FLOORS, stated because every UNMEASURED below is one of them.
MIN_STREAM_STEPS = 10    # out-of-sample trades a stream needs before it is scored
MIN_SCORED_STREAMS = 3   # scored streams needed before the cross-stream line is anything
MIN_T_N = 20             # pooled per-trade differences needed before a t-stat is printed
WARMUP = 5               # trades seen before the replay / expanding solve posts a fraction
#: Ceiling of the replay solve and of the plain grid: the desk's per-order hard limit
#: (`mt5desk.sizing.MAX_RISK_FRAC`), restated so a report leg imports nothing from the money path.
F_CAP = 0.10
GRID = np.linspace(0.0, F_CAP, 101)
REPLAY_SEED = 0
BASELINES = ("static_first", "static_expanding")
BASES = ("recorded", "replay")
HEADLINE_BASELINE = "static_first"


def plain_fraction(r: np.ndarray) -> float:
    """Grid argmax of mean log(1 + f r) on [0, F_CAP]: the no-posterior growth-optimal size."""
    r = np.asarray(r, dtype="float64")
    if r.size == 0:
        return 0.0
    best_f, best_g = 0.0, 0.0
    for f in GRID[1:]:
        x = 1.0 + f * r
        if np.any(x <= 0):
            break
        g = float(np.mean(np.log(x)))
        if g > best_g:
            best_f, best_g = float(f), g
    return best_f


def replay_fraction(r_prior: np.ndarray, kind: str = "live") -> float:
    """The LIVE posterior solve on the trades seen so far: what `robust_elog.optimise` would
    post for this sleeve alone. Live trades are credited as live days, forward as forward days,
    exactly the evidence weights `_posterior_mu` uses."""
    r = np.asarray(r_prior, dtype="float64")
    n = int(r.size)
    ev = [SleeveEvidence(name="s", daily_r=r,
                         live_days=n if kind == "live" else 0,
                         forward_days=n if kind != "live" else 0)]
    res = optimise(ev, hard_cap=F_CAP, target=None, cfg=WorldConfig(seed=REPLAY_SEED))
    return float(min(F_CAP, max(0.0, float(res.heat.get("s", 0.0)))))


def fractions(r: Sequence[float], recorded: Sequence[float | None] | None = None, *,
              kind: str = "live") -> dict[str, list[float | None]]:
    """Per trade, the fraction each book applies to it -- None where a book has none yet.

    NO LOOK-AHEAD, BY CONSTRUCTION: entry t of `replay` and `static_expanding` is computed from
    `r[:t]` and nothing else; entry t of `recorded` is the fraction stamped before trade t
    resolved. `tests/test_posterior_sizing_missed_growth.py` changes trade t and checks entry t
    of every book is unchanged.
    """
    a = np.asarray(list(r), dtype="float64")
    n = int(a.size)
    rec: list[float | None] = [None] * n
    for i, f in enumerate(list(recorded or [])[:n]):
        if isinstance(f, (int, float)) and math.isfinite(f) and f >= 0:
            rec[i] = float(f)
    replay: list[float | None] = [None] * n
    expanding: list[float | None] = [None] * n
    for t in range(WARMUP, n):
        replay[t] = replay_fraction(a[:t], kind)
        expanding[t] = plain_fraction(a[:t])
    return {"recorded": rec, "replay": replay, "static_expanding": expanding}


def _logw(f: float, r: float) -> float:
    return math.log(max(1e-12, 1.0 + f * r))


def score_stream(r: Sequence[float], recorded: Sequence[float | None] | None = None, *,
                 kind: str = "live") -> dict[str, Any]:
    """Both bases against both baselines on one stream. `diffs` are the per-trade log-growth
    differences (as sized minus static), kept for the pooled t-stat."""
    a = np.asarray(list(r), dtype="float64")
    fr = fractions(a, recorded, kind=kind)
    out: dict[str, Any] = {}
    for basis in BASES:
        fa = fr[basis]
        idx = [i for i, f in enumerate(fa) if f is not None]
        block: dict[str, Any] = {"n_with_fraction": len(idx)}
        if idx:
            block["first_fraction"] = round(float(fa[idx[0]] or 0.0), 8)
            block["last_fraction"] = round(float(fa[idx[-1]] or 0.0), 8)
            block["distinct_fractions"] = len({round(float(fa[i] or 0.0), 8) for i in idx})
        for base in BASELINES:
            if base == "static_first":
                steps = [(i, float(fa[idx[0]] or 0.0)) for i in idx[1:]]
            else:
                steps = [(i, float(fr["static_expanding"][i] or 0.0)) for i in idx
                         if fr["static_expanding"][i] is not None]
            if len(steps) < MIN_STREAM_STEPS:
                block[base] = {"status": UNMEASURED, "n": len(steps),
                               "why": f"{len(steps)} out-of-sample trade(s) with a {basis} "
                                      f"fraction < floor {MIN_STREAM_STEPS}"}
                continue
            la = [_logw(float(fa[i] or 0.0), float(a[i])) for i, _ in steps]
            lb = [_logw(fb, float(a[i])) for i, fb in steps]
            diffs = [x - y for x, y in zip(la, lb, strict=True)]
            delta = float(sum(diffs))
            block[base] = {"status": MEASURED, "n": len(steps),
                           "as_sized_logw": round(float(sum(la)), 8),
                           "static_logw": round(float(sum(lb)), 8),
                           "delta_logw": round(delta, 8),
                           "outcome": ("WIN" if delta > 1e-12 else
                                       "LOSS" if delta < -1e-12 else "TIE"),
                           "diffs": [round(d, 10) for d in diffs]}
        out[basis] = block
    return out


def sign_test_p(wins: int, n: int) -> float | None:
    """One-sided exact binomial P(X >= wins | n, 1/2); None when n == 0."""
    if n <= 0:
        return None
    return sum(math.comb(n, i) for i in range(wins, n + 1)) / 2.0 ** n


def t_stat(diffs: Sequence[float]) -> float | None:
    """Mean over standard error of the pooled per-trade differences; None under MIN_T_N or
    with no dispersion (a t-stat on a constant is not a number)."""
    d = np.asarray(list(diffs), dtype="float64")
    if d.size < MIN_T_N:
        return None
    sd = float(d.std(ddof=1))
    if not math.isfinite(sd) or sd <= 1e-15:
        return None
    return float(d.mean() / (sd / math.sqrt(d.size)))


def aggregate(streams: dict[str, dict[str, Any]], basis: str, base: str) -> dict[str, Any]:
    scored = [s[basis][base] for s in streams.values()
              if s.get(basis, {}).get(base, {}).get("status") == MEASURED]
    wins = sum(1 for s in scored if s["outcome"] == "WIN")
    losses = sum(1 for s in scored if s["outcome"] == "LOSS")
    ties = len(scored) - wins - losses
    pooled = [d for s in scored for d in s["diffs"]]
    doc: dict[str, Any] = {"scored_streams": len(scored), "wins": wins, "losses": losses,
                           "ties": ties, "n_trades": len(pooled)}
    if len(scored) < MIN_SCORED_STREAMS:
        return {**doc, "status": UNMEASURED,
                "why": f"{len(scored)} stream(s) reached {MIN_STREAM_STEPS} out-of-sample "
                       f"trades with a {basis} fraction; the floor is {MIN_SCORED_STREAMS}"}
    decided = wins + losses
    p_up = sign_test_p(wins, decided)
    p_down = sign_test_p(losses, decided)
    t = t_stat(pooled)
    delta = float(sum(s["delta_logw"] for s in scored))
    return {**doc, "status": MEASURED,
            "win_share": None if decided == 0 else round(wins / decided, 4),
            "delta_logw_sum": round(delta, 8),
            "delta_logw_per_trade": round(delta / len(pooled), 10) if pooled else None,
            "sign_test_p_as_sized_better": None if p_up is None else round(p_up, 6),
            "sign_test_p_static_better": None if p_down is None else round(p_down, 6),
            "t_stat": None if t is None else round(t, 4),
            "t_stat_note": None if t is not None else
            f"fewer than {MIN_T_N} pooled per-trade differences, or no dispersion"}


def is_significant(t: Any) -> bool:
    """True only for a MEASURED t-stat with |t| >= SIGNIFICANT_T. None, a bool, a string or a
    non-finite number is not a measurement and is never significant."""
    if isinstance(t, bool) or not isinstance(t, (int, float)):
        return False
    return math.isfinite(float(t)) and abs(float(t)) >= SIGNIFICANT_T


def missed_growth_line(aggs: dict[str, dict[str, dict[str, Any]]], at: str,
                       input_why: str | None = None) -> dict[str, Any]:
    """The signed line: E[log W] gained (+) or forgone (-) by sizing with the posterior rather
    than holding each sleeve at its first posted size. The first MEASURED basis is the headline;
    with none, UNMEASURED and the reason -- never a zero. The SIGN is published as a verdict
    (EARNS / COSTS) only when the pooled t-stat is measured and |t| >= SIGNIFICANT_T; otherwise
    the line is NOT_SIGNIFICANT, carrying the same value, t-stat and sign-test p."""
    base = HEADLINE_BASELINE
    line: dict[str, Any] = {"gate": "posterior_sizing", "at": at, "baseline": base,
                            "unit": "sum of realised log(1 + f r) over scored trades",
                            "sign": "+ the posterior-sized book gained; - it forwent growth"}
    for basis in BASES:
        ag = aggs[basis][base]
        if ag.get("status") != MEASURED:
            continue
        v = float(ag["delta_logw_sum"])
        t = ag["t_stat"]
        significant = is_significant(t)
        if significant:
            verdict, direction = (EARNS, "gained") if v > 0 else (COSTS, "forgone")
            why = (f"|t| = {abs(float(t)):.2f} >= {SIGNIFICANT_T:g} on the pooled per-trade "
                   f"differences: the sign of the summed delta is published; no size changes "
                   f"on it")
        else:
            verdict, direction = NOT_SIGNIFICANT, "not_significant"
            why = ((f"|t| = {abs(float(t)):.2f} < {SIGNIFICANT_T:g}" if t is not None else
                    "no t-stat (" + str(ag.get("t_stat_note")) + ")")
                   + ": the summed delta is a point estimate indistinguishable from zero, so "
                     "it is published as neither a gain nor a cost; no size changes on it")
        return {**line, "basis": basis,
                "basis_note": (None if basis == "recorded" else
                               "REPLAY, not the fraction the desk traded: the live solve re-run "
                               "per stream. recorded basis: "
                               + str(aggs["recorded"][base].get("why"))),
                "verdict": verdict, "direction": direction, "significant": significant,
                "significance_rule": f"|t_stat| >= {SIGNIFICANT_T:g} and the t-stat measured",
                "value": round(v, 8),
                "forgone_logw": round(max(0.0, -v), 8) if significant else None,
                "value_per_trade": ag["delta_logw_per_trade"],
                "n_streams": ag["scored_streams"], "n_trades": ag["n_trades"],
                "win_share": ag["win_share"],
                "sign_test_p": (ag["sign_test_p_as_sized_better"] if v >= 0
                                else ag["sign_test_p_static_better"]),
                "t_stat": t, "why": why}
    why = input_why or "; ".join(f"{b}: {aggs[b][base].get('why')}" for b in BASES)
    return {**line, "basis": None, "verdict": UNMEASURED, "direction": None, "value": None,
            "significant": False, "forgone_logw": None, "value_per_trade": None, "why": why}


# ------------------------------------------------------------------ inputs


def _key(name: Any) -> str:
    return name if isinstance(name, str) else "|".join(str(x) for x in name)


def _num(x: Any) -> float | None:
    return float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) \
        and math.isfinite(x) else None


def row_fraction(d: dict[str, Any]) -> float | None:
    """A fraction of equity at risk recorded ON the ledger row, or None. `risk_quote` with no
    equity is not one: it is money in the quote currency."""
    for k in ("risk_fraction", "risk_frac"):
        f = _num(d.get(k))
        if f is not None and f >= 0:
            return f
    risk, eq = _num(d.get("risk_usd")), _num(d.get("equity"))
    if risk is not None and eq is not None and eq > 0:
        return abs(risk) / eq
    return None


def load_decisions(path: Path = DECISIONS) -> dict[int, float] | None:
    """Broker ticket -> the allocator-book fraction `h` on its EXECUTED decision row. None when
    the ledger is absent (UNMEASURED), {} when it is present and carries no such row."""
    if not path.exists():
        return None
    out: dict[int, float] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if not isinstance(d, dict) or d.get("outcome") != "EXECUTED":
            continue
        ctx = d.get("portfolio_context")
        h = _num(ctx.get("h")) if isinstance(ctx, dict) else None
        t = d.get("ticket")
        if h is not None and h >= 0 and isinstance(t, int) and not isinstance(t, bool):
            out.setdefault(t, h)
    return out


def load_live(path: Path = LEDGER, decisions: dict[int, float] | None = None
              ) -> dict[Any, dict[str, Any]]:
    """Live streams in time order, keyed (account, sleeve) when the row carries an account so
    accounts are never pooled; deduped on the broker deal (else on account/sleeve/stamp) so a
    trade written twice counts once. Read through the audited ledger view."""
    if not path.exists():
        return {}
    rows: list[tuple[str, str, Any, float, float | None, str | None]] = []
    seen: set[Any] = set()
    for line in ledger_path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if not isinstance(d, dict):
            continue
        r = _num(d.get("r_multiple"))
        if not d.get("sleeve") or r is None or d.get("r_unreconstructible"):
            continue
        acct = d.get("account")
        sleeve = str(d["sleeve"])
        stamp = next((str(d[k]) for k in ("signal_time", "open_time", "entry_time", "time")
                      if d.get(k) not in (None, "")), "")
        deal = d.get("deal")
        ident: Any = (("deal", deal) if isinstance(deal, int) else
                      ("" if acct is None else str(acct), sleeve, stamp))
        if (isinstance(deal, int) or stamp) and ident in seen:
            continue
        seen.add(ident)
        frac, src = row_fraction(d), "ledger_row"
        if frac is None and decisions:
            for k in ("entry_order", "position_id", "order"):
                t = d.get(k)
                if isinstance(t, int) and t in decisions:
                    frac, src = decisions[t], "allocator_decision_h"
                    break
        key: Any = sleeve if acct is None else (str(acct), sleeve)
        rows.append((str(d.get("time", "") or stamp), _key(key), key, r, frac,
                     src if frac is not None else None))
    out: dict[Any, dict[str, Any]] = defaultdict(
        lambda: {"kind": "live", "r": [], "recorded": [], "sources": []})
    for _, _, k, r, frac, src in sorted(rows, key=lambda x: (x[0], x[1])):
        out[k]["r"].append(r)
        out[k]["recorded"].append(frac)
        out[k]["sources"].append(src)
    return dict(out)


def load_forward(shadow_dir: Path = SHADOW_DIR) -> dict[Any, dict[str, Any]]:
    """Forward-phase R per shadow clock (`reports/shadow/ledger_*.json`, written by
    `shadow_forward`). No capital stood behind these, so no fraction is recorded: replay only."""
    out: dict[Any, dict[str, Any]] = {}
    if not shadow_dir.is_dir():
        return out
    for p in sorted(shadow_dir.glob("ledger_*.json")):
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        rows = doc if isinstance(doc, list) else doc.get("rows") if isinstance(doc, dict) else None
        trades = sorted(
            (str(t.get("entry_time") or ""), float(t["r_multiple"]))
            for t in (rows or [])
            if isinstance(t, dict) and t.get("phase", "forward") == "forward"
            and _num(t.get("r_multiple")) is not None)
        if trades:
            out[("forward", p.stem[len("ledger_"):])] = {
                "kind": "forward", "r": [r for _, r in trades],
                "recorded": [None] * len(trades), "sources": [None] * len(trades)}
    return out


def evaluate(series: dict[Any, dict[str, Any]]) -> dict[str, Any]:
    streams: dict[str, dict[str, Any]] = {}
    for name, s in sorted(series.items(), key=lambda kv: _key(kv[0])):
        srcs = [x for x in s.get("sources", []) if x]
        streams[_key(name)] = {
            "kind": s.get("kind", "live"), "n": len(s["r"]),
            "recorded_fraction_sources": {k: srcs.count(k) for k in sorted(set(srcs))},
            **score_stream(s["r"], s.get("recorded"), kind=str(s.get("kind", "live")))}
    aggs = {b: {base: aggregate(streams, b, base) for base in BASELINES} for b in BASES}
    for s in streams.values():                       # the pooled diffs are in the aggregate
        for b in BASES:
            for base in BASELINES:
                s[b][base].pop("diffs", None)
    return {"streams": streams, "aggregate": aggs}


def build(ledger: Path = LEDGER, decisions: Path = DECISIONS,
          shadow_dir: Path = SHADOW_DIR) -> dict[str, Any]:
    at = datetime.now(UTC).isoformat()
    inputs: dict[str, Any] = {}
    input_why: str | None = None
    dec = load_decisions(decisions)
    inputs["decision_ledger"] = (
        {"status": UNMEASURED, "why": f"no {decisions.name} on this host: no allocator "
                                      f"fraction can be joined to a trade"} if dec is None
        else {"status": MEASURED, "executed_with_h": len(dec)})
    live: dict[Any, dict[str, Any]] = {}
    if not ledger.exists():
        inputs["live_ledger"] = {"status": UNMEASURED, "why": f"no {ledger.name} on this host"}
    else:
        try:
            live = load_live(ledger, dec)
            inputs["live_ledger"] = {"status": MEASURED, "streams": len(live),
                                     "trades": sum(len(s["r"]) for s in live.values())}
        except Exception as exc:
            inputs["live_ledger"] = {"status": UNMEASURED,
                                     "why": f"{type(exc).__name__}: {exc}"}
    fwd = load_forward(shadow_dir)
    inputs["forward_ledgers"] = (
        {"status": MEASURED, "streams": len(fwd),
         "trades": sum(len(s["r"]) for s in fwd.values())} if fwd
        else {"status": UNMEASURED,
              "why": f"no {shadow_dir.name}/ledger_*.json with a forward-phase R on this host"})
    series = {**live, **fwd}
    if not series:
        input_why = ("no trade stream on this host: " + "; ".join(
            f"{k}: {v['why']}" for k, v in inputs.items() if v.get("why")))
    res = evaluate(series)
    line = missed_growth_line(res["aggregate"], at, input_why)
    return {"schema": SCHEMA, "generated_at": at, "mode": "REPORT",
            "live_sizing_changed": False, "auto_promote": False,
            "status": line["verdict"] if line["verdict"] == UNMEASURED else MEASURED,
            "inputs": inputs,
            "floors": {"min_stream_steps": MIN_STREAM_STEPS,
                       "min_scored_streams": MIN_SCORED_STREAMS, "min_t_n": MIN_T_N,
                       "warmup_trades": WARMUP, "f_cap": F_CAP},
            "books": {
                "as_sized.recorded": "ledger-row fraction, else the allocator-book h on the "
                                     "EXECUTED decision joined by ticket (a target, not a fill)",
                "as_sized.replay": "robust_elog.optimise on the stream's own trades 1..t "
                                   "(single sleeve; per-trade R as daily R)",
                "static_first": "the first posted fraction held fixed (headline baseline)",
                "static_expanding": "plain growth-optimal grid fraction on trades 1..t "
                                    "(not scale-matched to recorded fractions)"},
            "missed_growth_line": line, "missed_growth": [line], **res}


def main() -> int:
    doc = build()
    write_text_resilient(OUT, json.dumps(doc, indent=1, sort_keys=True))
    ln = doc["missed_growth_line"]
    print(json.dumps({"status": doc["status"], "basis": ln.get("basis"),
                      "verdict": ln["verdict"], "value": ln.get("value"),
                      "why": ln.get("why")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
