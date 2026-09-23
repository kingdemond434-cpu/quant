"""Drift AHEAD: forecast the next window's distribution per instrument, and ask whether the
book's correlation topology has moved -- before the drawdown teaches it.

TWO DRIFTS, ONE VERDICT. Per instrument, `libs.regime.drift` summarises each broker day of H1
bars by declared statistics (vol, range, breakout hit-rate, spread rank, |ret|), fits a learned
lag weighting on how past windows predicted their successors, and reports the NEXT window's
forecast as a z against the long-run baseline. `hazard_max` is the largest |z| across the
statistics; measured 2026-09-04 on the desk's own bars it sits at 0.81 (EURUSD), 0.81 (XAUUSD)
and 0.91 (USDJPY) -- STABLE, and below the WATCH line at 1.0 by a margin that says the line is
not decorative. Per book, `libs.portfolio.latent_factors.drift` asks whether the recent 30 days'
sleeve correlation matrix sits farther from the EW long-run matrix than past 30-day blocks did,
in units of those blocks' own dispersion; `tail_dependence` and the k-factor model are reported
recent-vs-prior beside it, because the bad-state picture is the one capital is sized on.

    verdict = STRUCTURE_SHIFTED   the book's correlation topology moved (structure z > 2)
            | DRIFT_AHEAD         some instrument's forecast hazard_max > 2
            | WATCH               some instrument's hazard_max > 1
            | STABLE              nothing above the lines

THE REPORT IS THE PRODUCT. No tasks leave here. `revival_engine` reads `verdict` from
reports/DRIFT.json to decide whether STATE_FRAGILE burials deserve a second look, and the
allocator's crisis overlay is the other intended listener. `what_changed` is the compact list of
(symbol, statistic, z) that moved, so a reader does not have to walk per_symbol to learn why.

THE THIRD DRIFT (2026-09-05): PER-SLEEVE EDGE HAZARD.

    "Monitoring loop: prediction decay, PnL decay, state decay, cost drift, fill drift, factor
     drift, feature drift, relationship drift; hazard_i(t) = P(edge breaks next horizon |
     history); allocation changes BEFORE the formal retirement threshold."   -- the principal

The two drifts above are about the MARKET (this instrument's next window) and the BOOK (the
correlation topology). Neither answers the question capital is actually sized on: is THIS SLEEVE's
edge breaking? `hazard_by_sleeve` answers it by reading the nine monitored channels out of the
ledgers the desk already keeps -- forward expectancy against the certificate, recent P&L against
the sleeve's own earlier half, the admission verdicts the conditioning depends on, the execution
twin's realised slip and fill rate against what the simulator charged, the two drifts this file
already computes, the cross-asset graph's sign stability, and `crowding_hazard.hazard` (which had
no importer on this desk until now) -- and combining them through `libs.research.perishability`.

WHY IT LIVES HERE AND NOT IN A NEW ORGAN. Four of the nine channels are numbers this pass has
already computed and would otherwise be recomputed from the same bars by a second reader; the
scheduler, the report and the degraded list are already here. The COMBINATION rule is not here --
it is `perishability.edge_hazard`, so the rule can be tested without bars, a ledger or a clock.

RETIREMENT IS STILL SOMEBODY ELSE'S DECISION. This publishes `hazard_by_sleeve` into
reports/DRIFT.json. The principal's "allocation changes BEFORE the formal retirement threshold"
is the ALLOCATOR's move to make on this number; nothing here shrinks, fades or retires anything.

DEGRADES WITH A REASON, NEVER SILENTLY. Off-box (measured 2026-09-04) the canon still names 14
book instruments but the shadow ledgers hold 14 days of 50 sleeves against the 90 rows structure
drift needs, so the verdict was WATCH on EURGBP's range forecast (z = -1.06) with structure
UNMEASURED and the reason written beside it. A tree with no canon falls back to the instruments
that have bars; every such substitution is a `why` string on the report and a line in
`degraded`, and the verdict is computed from whatever WAS measurable.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.portfolio import latent_factors as lf  # noqa: E402
from libs.regime.drift import forecast_next, window_stats  # noqa: E402
from libs.research import crowding_hazard as ch  # noqa: E402
from libs.research import perishability as ph  # noqa: E402
from research import proposer_common as pc  # noqa: E402

REPORT = _DESK / "reports" / "DRIFT.json"
CANON = _DESK / "data" / "UNIVERSAL_SURVIVORS.canon.json"
STATE_ADMISSION = _DESK / "reports" / "STATE_ADMISSION.json"
EXECUTION_TWIN = _DESK / "reports" / "EXECUTION_TWIN.json"
CROSS_ASSET = _DESK / "reports" / "CROSS_ASSET_GRAPH.json"
#: The family whose shadow ledgers are named `<sym>_<window>` rather than `<sym>_<fam>_<window>`
#: (shadow_forward.py:647). Declared here so the canon-to-ledger join is one named exception
#: rather than a guess repeated at every call site.
FLAT_LEDGER_FAMILY = "session_range_breakout"
#: Trades a sleeve needs before its two halves are compared. Below this the "recent half" is
#: three trades and its mean is a coin flip wearing a decay verdict.
MIN_SLEEVE_TRADES = 2 * ph.HAZARD_MIN_N
#: One window is one broker day of H1 bars: the clock the allocator re-sizes on.
WINDOW = 24
#: Windows the forecast is fitted on. 750 days is the long-run baseline the hazard is measured
#: against -- long enough that one quarter's vol regime does not become "normal", short enough
#: to stay bounded on a 53,899-bar frame (the fit itself is a least-squares on 750 rows).
LOOKBACK_BARS = WINDOW * 750
MIN_BARS = 3000
#: Fallback breadth when the certified book is empty (off-box): enough instruments to see a
#: market-wide move, few enough that the report stays readable.
FALLBACK_CAP = 12
#: Structure drift compares the last RECENT_DAYS of daily sleeve P&L with the long run. 30 is the
#: shortest window on which a 50-sleeve correlation matrix is a matrix rather than noise, and
#: `latent_factors.drift` needs three such blocks of history before it will say anything.
RECENT_DAYS = 30
MIN_SLEEVES = 2
WATCH_Z, DRIFT_Z = 1.0, 2.0
STABLE, WATCH, DRIFT_AHEAD, STRUCTURE_SHIFTED, UNMEASURED = (
    "STABLE", "WATCH", "DRIFT_AHEAD", "STRUCTURE_SHIFTED", "UNMEASURED")


def _book_symbols() -> list[str]:
    try:
        from research.state_vector_build import book_symbols
        return book_symbols()
    except Exception:
        return []


def _n_bars(path: Path) -> int:
    """Row count from the parquet footer, so choosing a fallback set does not load 24 frames."""
    try:
        import pyarrow.parquet as pq
        return int(pq.read_metadata(path).num_rows)
    except Exception:
        d = pc.bars(path.stem.removesuffix("_H1"))
        return 0 if d is None else len(d)


def _symbols(symbols: list[str] | None) -> tuple[list[str], dict[str, str]]:
    """Which instruments to watch, and why those. Explicit > certified book > fallback."""
    have = {p.stem.removesuffix("_H1"): p for p in pc.UNI.glob("*_H1.parquet")}
    if symbols:
        return sorted({s for s in symbols if s in have}), {"source": "explicit", "why": ""}
    book = [s for s in _book_symbols() if s in have]
    if book:
        return sorted(set(book)), {"source": "book", "why": ""}
    fallback = sorted(s for s, p in have.items() if _n_bars(p) >= MIN_BARS)[:FALLBACK_CAP]
    return fallback, {"source": "fallback",
                      "why": (f"certified book empty on this tree; watching up to {FALLBACK_CAP} "
                              f"instruments with >= {MIN_BARS} H1 bars instead")}


def symbol_drift(d: pd.DataFrame) -> dict[str, Any]:
    """Next-window forecast hazard for one instrument, from its own declared statistics."""
    stats = window_stats(d.tail(LOOKBACK_BARS), window=WINDOW)
    fc = forecast_next(stats)
    per_stat = {col: {k: v for k, v in row.items() if k in ("forecast", "baseline", "z")}
                for col, row in (fc.get("per_stat") or {}).items()}
    return {"hazard_max": fc.get("hazard_max"), "verdict": fc.get("verdict") or UNMEASURED,
            "hazard": fc.get("hazard") or {}, "per_stat": per_stat, "n_windows": len(stats),
            "why": fc.get("why", "")}


def _load_trades() -> list[Any]:
    try:
        from research.state_admission_run import load_trades
        return list(load_trades("shadow"))
    except Exception:
        return []


def daily_pnl_matrix(trades: list[Any]) -> tuple[np.ndarray | None, list[str], str]:
    """Days x sleeves of realised shadow R, zero where a sleeve did not trade that day.

    Zero-filling is the honest choice for a correlation of OUTCOMES: a sleeve that sat out a day
    earned nothing on it, and leaving NaN would let pandas compute each pair on a different set
    of days and call the result one matrix.
    """
    rows = []
    for t in trades:
        try:
            when = pd.Timestamp(t.when)
            when = when.tz_localize("UTC") if when.tzinfo is None else when.tz_convert("UTC")
            rows.append((str(t.sleeve), when.normalize(), float(t.r)))
        except (TypeError, ValueError, AttributeError):
            continue
    if not rows:
        return None, [], "no shadow trades: no ledger_*.json under reports/shadow or backups"
    frame = pd.DataFrame(rows, columns=["sleeve", "day", "r"])
    piv = frame.pivot_table(index="day", columns="sleeve", values="r", aggfunc="sum",
                            fill_value=0.0).sort_index()
    sleeves = [str(c) for c in piv.columns]
    if len(sleeves) < MIN_SLEEVES:
        return None, sleeves, f"need {MIN_SLEEVES} sleeves for a correlation, have {len(sleeves)}"
    return piv.to_numpy(dtype=float), sleeves, ""


def structure_drift(m: np.ndarray | None, sleeves: list[str], why: str = "") -> dict[str, Any]:
    """Has the book's latent-factor structure moved? recent RECENT_DAYS vs the long run."""
    if m is None:
        return {"verdict": UNMEASURED, "z": None, "why": why or "no P&L matrix"}
    dr = lf.drift(m, recent=RECENT_DAYS)
    out: dict[str, Any] = {"verdict": dr.get("verdict") or UNMEASURED, "z": dr.get("z"),
                           "distance": dr.get("distance"), "baseline_mean": dr.get("baseline_mean"),
                           "windows": dr.get("windows"), "why": dr.get("why", ""),
                           "n_days": int(m.shape[0]), "n_sleeves": int(m.shape[1]),
                           "recent_days": RECENT_DAYS}
    if m.shape[0] < 2 * RECENT_DAYS:
        out["tail_dependence"] = {"why": f"need {2 * RECENT_DAYS} days for recent-vs-prior"}
        return out
    now, prior = m[-RECENT_DAYS:], m[:-RECENT_DAYS]
    off = ~np.eye(m.shape[1], dtype=bool)
    try:
        td_now, td_prior = lf.tail_dependence(now), lf.tail_dependence(prior)
        out["tail_dependence"] = {
            "recent_mean": round(float(td_now[off].mean()), 4),
            "prior_mean": round(float(td_prior[off].mean()), 4),
            "recent_max": round(float(td_now[off].max()), 4),
            "prior_max": round(float(td_prior[off].max()), 4)}
        k = int(min(3, m.shape[1]))
        out["factor_explained"] = {
            "recent": round(float(lf.factor_model(now, k=k)["explained"]), 4),
            "prior": round(float(lf.factor_model(prior, k=k)["explained"]), 4)}
        # THE FOUR HEATS ON AN EQUAL-WEIGHT BOOK: what 1/N nominal is really made of today. The
        # allocator sizes its own book; this is the structure's own statement, weight-free.
        ev = [SimpleNamespace(name=s, daily_r=m[:, i]) for i, s in enumerate(sleeves)]
        heats = lf.effective(ev, {s: 1.0 / len(sleeves) for s in sleeves})
        out["heats_equal_weight"] = {k: heats.get(k) for k in (
            "nominal", "covariance", "factor", "tail", "effective", "n_eff",
            "factor_explained", "max_tail_dependence", "stress_days")}
    except Exception as exc:
        out["tail_dependence"] = {"why": f"{type(exc).__name__}: {exc}"}
    return out


# --------------------------------------------------------------------------- edge hazard
def _json(path: Path) -> dict[str, Any]:
    """A desk report as a dict, or an empty one. An unreadable ledger is an UNMEASURED channel,
    never a crash and never a zero -- every caller here says which."""
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _num(v: Any) -> float | None:
    if isinstance(v, bool) or v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if np.isfinite(f) else None


def symbol_of(sleeve: str) -> str:
    """The instrument a sleeve trades, from its name -- the desk's own convention (excursions,
    exit_accounts and state_admission all split on the first underscore)."""
    return str(sleeve).split("_")[0].upper()


def certified_expectancy(path: Path = CANON) -> dict[str, float]:
    """Per shadow-ledger sleeve, the expectancy its certificate CLAIMED, in R per trade.

    The join is the one shadow_forward makes when it names a ledger: `<sym>_<window>` for the
    founding family and `<sym>_<family>_<window>` for every other. Several certified cells (long
    and short, one condition each) can share a ledger, so their claims are AVERAGED and the count
    is kept -- a sleeve whose ledger pools four cells is being asked to deliver their mean, which
    is what it is actually trading.
    """
    doc = _json(path)
    claims: dict[str, list[float]] = {}
    for row in (doc.get("survivors") or {}).values():
        if not isinstance(row, dict):
            continue
        spec = row.get("shadow_spec") or {}
        sym, fam = str(spec.get("symbol") or ""), str(spec.get("family") or "")
        win = str(spec.get("selector") or "")
        ev = _num(((row.get("gates") or {}).get("expected_value") or {}).get("ev"))
        if not sym or not win or ev is None:
            continue
        name = f"{sym}_{win}" if fam == FLAT_LEDGER_FAMILY else f"{sym}_{fam}_{win}"
        claims.setdefault(name, []).append(ev)
    return {k: float(np.mean(v)) for k, v in claims.items()}


def trades_by_sleeve(trades: list[Any]) -> dict[str, list[float]]:
    """Per sleeve, its realised R in entry order -- the series both decay channels read."""
    out: dict[str, list[tuple[Any, float]]] = {}
    for t in trades:
        try:
            out.setdefault(str(t.sleeve), []).append((pd.Timestamp(t.when), float(t.r)))
        except (TypeError, ValueError, AttributeError):
            continue
    return {k: [r for _, r in sorted(v, key=lambda x: x[0])] for k, v in out.items()}


def prediction_decay(sleeve: str, rs: list[float], claims: dict[str, float]) -> ph.Pressure:
    """Forward expectancy against the expectancy the ten gates certified.

    This is the channel the principal named first and the one the desk had no line for: a sleeve
    delivering a quarter of what its certificate claimed is three quarters of the way to gone,
    whatever its t-statistic is doing.
    """
    ev = claims.get(sleeve)
    if ev is None:
        return ph.unmeasured_pressure(
            "prediction_decay", f"no certificate claim joins ledger {sleeve} in "
            f"{CANON.name}; the certified expectancy is what forward is measured against",
            len(rs))
    fwd = float(np.mean(rs)) if rs else None
    return ph.decay_pressure("prediction_decay", fwd, ev, len(rs), cells_pooled=1)


def pnl_decay(rs: list[float]) -> ph.Pressure:
    """The sleeve's recent half against its own earlier half, in R per trade.

    Split on TRADE COUNT rather than on the calendar so a sleeve that trades twice a week and one
    that trades twice a day are compared on the same amount of evidence, not the same span.
    """
    n = len(rs)
    if n < MIN_SLEEVE_TRADES:
        return ph.unmeasured_pressure("pnl_decay", f"{n} trade(s), need {MIN_SLEEVE_TRADES} to "
                                                   "split into two halves", n)
    half = n // 2
    prior, recent = rs[:half], rs[half:]
    return ph.decay_pressure("pnl_decay", float(np.mean(recent)), float(np.mean(prior)),
                             len(recent), n_prior=len(prior))


def state_decay(path: Path = STATE_ADMISSION) -> ph.Pressure:
    """How much of the conditioning the book sizes on has stopped predicting out of sample.

    The admission gauntlet re-judges every dimension each pass, so a dimension that has slipped
    from ADMIT to RETAIN_SHRUNK or into the graveyard IS the verdict change the principal asked
    to be monitored. Weighted by test trades, so a dimension judged on 300 trades outvotes one
    judged on 20 rather than counting as one dimension each.
    """
    adm = _json(path)
    verdicts = adm.get("verdicts") or {}
    if not verdicts:
        return ph.unmeasured_pressure("state_decay",
                                      f"{path.name} absent on this host: the admission verdicts "
                                      "are what a state decay would be measured against")
    lost, total = 0.0, 0.0
    detail: dict[str, Any] = {}
    skipped: list[str] = []
    for dim, row in verdicts.items():
        if not isinstance(row, dict):
            continue
        n_test = _num(row.get("n_test")) or 0.0
        v = str(row.get("verdict") or "")
        gain = _num(row.get("mse_gain"))
        if v == "UNJUDGED":
            # The gauntlet could not judge it at all (one bucket ever reached the training
            # floor). That is not a decayed dimension and not a healthy one; counting it either
            # way would put an absence of evidence into a pressure. Named and set aside.
            skipped.append(str(dim))
            detail[str(dim)] = {"verdict": v, "mse_gain": gain, "n_test": int(n_test),
                                "decayed": None, "why": str(row.get("why") or "")}
            continue
        # A dimension is DECAYED when the gauntlet buried it, or when conditioning on it now
        # makes the out-of-sample prediction worse than not conditioning at all.
        decayed = v == "GRAVEYARD" or (gain is not None and gain < 0.0)
        total += n_test
        lost += n_test if decayed else 0.0
        detail[str(dim)] = {"verdict": v, "mse_gain": gain, "n_test": int(n_test),
                            "decayed": decayed}
    if total <= 0:
        return ph.unmeasured_pressure(
            "state_decay", ("every judged dimension is UNJUDGED "
                            f"({', '.join(skipped)}): no state evidence either way" if skipped
                            else "no dimension carries test trades"), 0, dimensions=detail)
    return ph.share_pressure("state_decay", lost / total, int(total), dimensions=detail,
                             unjudged=skipped)


def relationship_drift(path: Path = CROSS_ASSET) -> ph.Pressure:
    """Cross-asset sign agreement: does the driver graph still point the way it pointed?

    `stability` on a cross-asset edge is the share of sub-windows whose sign agreed with the
    full-sample one, which is exactly the relationship-drift measurement the principal named.
    Averaged across the graph's edges, because an edge's own instability is that edge's business
    and the book's exposure is to the graph.
    """
    doc = _json(path)
    edges = doc.get("edges")
    if not isinstance(edges, list) or not edges:
        return ph.unmeasured_pressure("relationship_drift",
                                      f"{path.name} carries no edges on this host")
    st = [s for e in edges if isinstance(e, dict) and (s := _num(e.get("stability"))) is not None]
    if not st:
        return ph.unmeasured_pressure("relationship_drift",
                                      "no edge carries a stability", len(edges))
    return ph.agreement_pressure("relationship_drift", float(np.mean(st)), len(st),
                                 n_edges=len(edges))


def twin_symbols(path: Path = EXECUTION_TWIN) -> dict[str, dict[str, Any]]:
    """Per symbol, the twin's realised-versus-modelled slip and fill rows."""
    rows = ((_json(path).get("recalibration") or {}).get("symbols") or {})
    return {str(k): v for k, v in rows.items() if isinstance(v, dict)}


def cost_drift(sym: str, twin: dict[str, dict[str, Any]]) -> ph.Pressure:
    """Realised one-way slip against what the simulator charged when the edge was certified.

    The twin is the right reference precisely because it is what the GAUNTLET believed: an edge
    whose live cost has doubled against the cost it was certified under has lost the margin it
    was certified on, whether or not its P&L has noticed yet.
    """
    row = (twin.get(sym) or {}).get("slip") or {}
    if not row:
        return ph.unmeasured_pressure("cost_drift", f"{sym} has no execution-twin slip row "
                                                    f"({EXECUTION_TWIN.name})")
    return ph.ratio_pressure("cost_drift", _num(row.get("realised_frac")),
                             _num(row.get("modelled_frac")), int(_num(row.get("n")) or 0),
                             worse_is_higher=True, twin_verdict=row.get("verdict"))


def fill_drift(sym: str, twin: dict[str, dict[str, Any]]) -> ph.Pressure:
    """Realised fill rate of resting orders against the rate the simulator predicted.

    A fill rate that has fallen is the queue lengthening: the same signal, later in the book. It
    is a leading indicator of decay, not a plumbing complaint, which is why it sits here beside
    prediction decay rather than only in the execution reports.
    """
    row = (twin.get(sym) or {}).get("fill") or {}
    if not row:
        return ph.unmeasured_pressure("fill_drift", f"{sym} has no execution-twin fill row "
                                                    f"({EXECUTION_TWIN.name})")
    return ph.ratio_pressure("fill_drift", _num(row.get("realised_rate")),
                             _num(row.get("predicted_mean")), int(_num(row.get("n")) or 0),
                             worse_is_higher=False, twin_verdict=row.get("verdict"))


def feature_drift(sym: str, per_symbol: dict[str, dict[str, Any]]) -> ph.Pressure:
    """The instrument's own next-window forecast hazard, already computed by this pass.

    A sleeve's features ARE the instrument's declared statistics -- vol, range, breakout hit
    rate, spread rank -- so `hazard_max` is the feature drift, read on the drift monitor's own
    WATCH and DRIFT lines rather than a second private pair.
    """
    row = per_symbol.get(sym) or {}
    z, n = _num(row.get("hazard_max")), int(_num(row.get("n_windows")) or 0)
    if z is None:
        return ph.unmeasured_pressure("feature_drift",
                                      f"{sym} not measured this pass (no bars, or skipped)", n)
    return ph.drift_pressure("feature_drift", z, n, watch=WATCH_Z, broken=DRIFT_Z + 1.0,
                             stats=sorted((row.get("per_stat") or {}).keys()))


def factor_drift(structure: dict[str, Any]) -> ph.Pressure:
    """The book's correlation topology against its own history -- this pass's structure z."""
    z = _num(structure.get("z"))
    n = int(_num(structure.get("n_days")) or 0)
    if z is None:
        return ph.unmeasured_pressure("factor_drift",
                                      str(structure.get("why") or "structure drift unmeasured"), n)
    return ph.drift_pressure("factor_drift", z, n, watch=WATCH_Z, broken=DRIFT_Z + 1.0,
                             structure_verdict=structure.get("verdict"))


def crowding(sym: str, twin: dict[str, dict[str, Any]],
             per_symbol: dict[str, dict[str, Any]]) -> ph.Pressure:
    """`crowding_hazard.hazard` on a state built from THIS desk's book evidence.

    That module has been correct and unimported since it was written: it wants a strategy's
    spread, fill and impact NOW as ratios to its own baseline, and the desk has all three --
    spread rank from this pass's own forecast against its long-run baseline, fill rate and slip
    from the execution twin's realised-versus-modelled rows. It returns a PROBABILITY over the
    horizon; `perishability.pressure_from_hazard` inverts it through the same declared scale so
    the crowding channel weighs exactly what the other eight do.

    Its own floor (60 paired observations) is respected: below it the module returns None with a
    reason and this channel is UNMEASURED, which is the honest answer and a visible one.
    """
    slip = (twin.get(sym) or {}).get("slip") or {}
    fill = (twin.get(sym) or {}).get("fill") or {}
    stats = (per_symbol.get(sym) or {}).get("per_stat") or {}
    spread = stats.get("spread_rank") or {}
    fc, base = _num(spread.get("forecast")), _num(spread.get("baseline"))
    spread_ratio = (fc / base) if fc is not None and base not in (None, 0.0) else 1.0
    slip_now, slip_model = _num(slip.get("realised_frac")), _num(slip.get("modelled_frac"))
    impact = (slip_now / slip_model) if slip_now is not None and slip_model else 1.0
    rate, pred = _num(fill.get("realised_rate")), _num(fill.get("predicted_mean"))
    fill_ratio = (rate / pred) if rate is not None and pred else 1.0
    obs = int(min(_num(slip.get("n")) or 0.0, _num(fill.get("n")) or 0.0))
    state = ch.CrowdingState(strategy_id=sym, observations=obs,
                             spread_ratio=float(spread_ratio), impact_ratio=float(impact),
                             fill_rate_ratio=float(fill_ratio))
    p, why = ch.hazard(state, horizon_days=ph.HAZARD_HORIZON_DAYS)
    if p is None:
        return ph.unmeasured_pressure("crowding", why, obs)
    return ph.Pressure("crowding", ph.pressure_from_hazard(p), obs, "",
                       {"crowding_hazard": round(p, 6), "spread_ratio": round(spread_ratio, 4),
                        "impact_ratio": round(impact, 4), "fill_rate_ratio": round(fill_ratio, 4),
                        "why": why})


def hazard_by_sleeve(per_symbol: dict[str, dict[str, Any]], structure: dict[str, Any],
                     trades: list[Any], claims: dict[str, float] | None = None,
                     twin: dict[str, dict[str, Any]] | None = None,
                     shared: list[ph.Pressure] | None = None) -> dict[str, Any]:
    """hazard_i(t) = P(edge breaks next horizon | history), one row per sleeve with a ledger.

    Three channels are the BOOK's and shared by every sleeve (state, factor and relationship
    drift are properties of the conditioning, the covariance and the driver graph, not of one
    sleeve); the rest are the sleeve's own. Shared channels are still listed per sleeve with
    their n, so a reader never has to hold two tables in their head to know what a hazard stands
    on. Every ledger is injectable so the combination can be tested without a desk tree.
    """
    claims = certified_expectancy() if claims is None else claims
    twin = twin_symbols() if twin is None else twin
    if shared is None:
        shared = [state_decay(), factor_drift(structure), relationship_drift()]
    # BOOK-scoped, so a hazard cannot be built out of them alone. Measured 2026-09-05: off-box
    # `state_decay` was the ONLY readable channel, and averaging it by itself put 23 sleeves at
    # 52.8% BREAKING -- one fact about the conditioning wearing 23 per-edge costumes.
    shared = [ph.book_scope(p) for p in shared]
    by_sleeve = trades_by_sleeve(trades)
    out: dict[str, Any] = {}
    for sleeve, rs in sorted(by_sleeve.items()):
        sym = symbol_of(sleeve)
        parts = [prediction_decay(sleeve, rs, claims), pnl_decay(rs),
                 shared[0], cost_drift(sym, twin), fill_drift(sym, twin), shared[1],
                 feature_drift(sym, per_symbol), shared[2], crowding(sym, twin, per_symbol)]
        row = ph.edge_hazard(parts)
        row.update({"symbol": sym, "n_trades": len(rs)})
        out[sleeve] = row
    return out


def hazard_summary(rows: dict[str, Any]) -> dict[str, Any]:
    """The compact answer a consumer reads: who is breaking, on how much evidence."""
    scored = {k: v for k, v in rows.items() if v.get("hazard") is not None}
    top = max(scored.items(), key=lambda kv: kv[1]["hazard"], default=None)
    return {
        "n_sleeves": len(rows), "n_measured": len(scored),
        "n_unmeasured": len(rows) - len(scored),
        "max": ({"sleeve": top[0], "hazard": top[1]["hazard"],
                 "verdict": top[1]["verdict"], "leading_channel": top[1].get("leading_channel"),
                 "n_measured_channels": top[1]["n_measured"]} if top else None),
        "breaking": sorted(k for k, v in scored.items() if v["verdict"] == ph.BREAKING),
        "at_risk": sorted(k for k, v in scored.items() if v["verdict"] == ph.AT_RISK),
        "horizon_days": ph.HAZARD_HORIZON_DAYS,
        "channels": list(ph.HAZARD_COMPONENTS),
        "lines": {"at_risk": ph.HAZARD_AT_RISK, "breaking": ph.HAZARD_BREAKING,
                  "scale_days": ph.HAZARD_SCALE_DAYS, "min_n": ph.HAZARD_MIN_N},
        "rule": ("hazard_i(t) = 1 - exp(-(mean measured pressure / scale_days) x horizon_days); "
                 "an unmeasured channel is named, never averaged in as zero. This NAMES the "
                 "hazard; the allocator shrinks on it and retirement stays a separate decision."),
    }


def what_changed(per_symbol: dict[str, dict[str, Any]], structure: dict[str, Any],
                 limit: int = 40) -> list[dict[str, Any]]:
    """The compact answer to 'why this verdict': every (symbol, statistic) past the WATCH line."""
    out: list[dict[str, Any]] = []
    for sym, row in per_symbol.items():
        for stat, s in (row.get("per_stat") or {}).items():
            z = s.get("z")
            if z is not None and abs(float(z)) >= WATCH_Z:
                out.append({"symbol": sym, "stat": stat, "z": float(z),
                            "forecast": s.get("forecast"), "baseline": s.get("baseline")})
    z = structure.get("z")
    if z is not None and float(z) >= WATCH_Z:
        out.append({"symbol": "BOOK", "stat": "correlation_structure", "z": float(z),
                    "forecast": structure.get("distance"),
                    "baseline": structure.get("baseline_mean")})
    out.sort(key=lambda r: -abs(r["z"]))
    return out[:limit]


def verdict(per_symbol: dict[str, dict[str, Any]], structure: dict[str, Any]) -> str:
    """STRUCTURE_SHIFTED outranks the per-instrument lines: a book whose sleeves have collapsed
    onto one factor is the larger fact whatever any single instrument's vol is doing next."""
    if structure.get("verdict") == STRUCTURE_SHIFTED:
        return STRUCTURE_SHIFTED
    hz = [float(r["hazard_max"]) for r in per_symbol.values() if r.get("hazard_max") is not None]
    if hz and max(hz) > DRIFT_Z:
        return DRIFT_AHEAD
    if hz and max(hz) > WATCH_Z:
        return WATCH
    return STABLE


def run(symbols: list[str] | None = None, budget_s: float = 300.0, write: bool = True) -> dict:
    todo, chosen = _symbols(symbols)
    per_symbol: dict[str, dict[str, Any]] = {}
    skipped: dict[str, str] = {}
    degraded: list[str] = []
    if chosen["why"]:
        degraded.append(chosen["why"])
    started = time.monotonic()
    for sym in todo:
        if time.monotonic() - started > budget_s:
            skipped[sym] = "budget exhausted"
            continue
        d = pc.bars(sym)
        if d is None or len(d) < MIN_BARS:
            skipped[sym] = f"under {MIN_BARS} H1 bars"
            continue
        try:
            per_symbol[sym] = symbol_drift(d)
        except Exception as exc:
            skipped[sym] = f"{type(exc).__name__}: {exc}"
    if not per_symbol:
        degraded.append("no instrument measured: per-symbol hazard absent from the verdict")
    trades = _load_trades()
    m, sleeves, why = daily_pnl_matrix(trades)
    structure = structure_drift(m, sleeves, why)
    if structure.get("verdict") == UNMEASURED or structure.get("z") is None:
        degraded.append(f"structure drift unmeasured: {structure.get('why') or 'no z'}")
    try:
        haz = hazard_by_sleeve(per_symbol, structure, trades)
    except Exception as exc:                    # a broken ledger is a reading, not a failed pass
        haz = {}
        degraded.append(f"hazard_by_sleeve failed: {type(exc).__name__}: {exc}")
    hz_sum = hazard_summary(haz)
    if not haz:
        degraded.append("no sleeve carries a realised ledger: hazard_by_sleeve is empty")
    elif not hz_sum["n_measured"]:
        degraded.append(f"{len(haz)} sleeve(s) carry no measured hazard channel")
    sym_hz = [float(r["hazard_max"]) for r in per_symbol.values()
              if r.get("hazard_max") is not None]
    doc = {"generated_utc": datetime.now(tz=UTC).isoformat(),
           "verdict": verdict(per_symbol, structure),
           "symbol_verdict": (DRIFT_AHEAD if sym_hz and max(sym_hz) > DRIFT_Z else
                              WATCH if sym_hz and max(sym_hz) > WATCH_Z else
                              STABLE if sym_hz else UNMEASURED),
           "structure_verdict": structure.get("verdict") or UNMEASURED,
           "hazard_max": (round(max(sym_hz), 3) if sym_hz else None),
           "per_symbol": per_symbol, "structure": structure,
           "hazard_by_sleeve": haz, "hazard_summary": hz_sum,
           "what_changed": what_changed(per_symbol, structure),
           "symbols": {**chosen, "n": len(todo)}, "skipped": skipped, "degraded": degraded,
           "lines": {"watch_z": WATCH_Z, "drift_z": DRIFT_Z, "window_bars": WINDOW,
                     "lookback_bars": LOOKBACK_BARS, "recent_days": RECENT_DAYS},
           "rule": ("STRUCTURE_SHIFTED if the book's correlation topology moved (structure z > "
                    f"{DRIFT_Z}); else DRIFT_AHEAD if any instrument's next-window hazard_max > "
                    f"{DRIFT_Z}; else WATCH if > {WATCH_Z}; else STABLE. `hazard_by_sleeve` is "
                    "the separate per-edge question -- P(this sleeve's edge breaks within "
                    f"{ph.HAZARD_HORIZON_DAYS:g} days | history) over "
                    f"{len(ph.HAZARD_COMPONENTS)} named channels. Consumers: revival_engine "
                    "(STATE_FRAGILE burials), the allocator's crisis overlay and its "
                    "pre-retirement shrink.")}
    if write:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    return doc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", action="append", default=None)
    ap.add_argument("--budget-s", type=float, default=300.0)
    ap.add_argument("--no-write", action="store_true")
    a = ap.parse_args()
    doc = run(symbols=a.symbol, budget_s=a.budget_s, write=not a.no_write)
    print(f"DRIFT  verdict={doc['verdict']}  symbols={doc['symbol_verdict']} "
          f"(hazard_max={doc['hazard_max']})  structure={doc['structure_verdict']} "
          f"(z={doc['structure'].get('z')})  watched={doc['symbols']['n']} "
          f"[{doc['symbols']['source']}]")
    for r in doc["what_changed"][:12]:
        print(f"  {r['symbol']:10s} {r['stat']:22s} z={r['z']:+.2f}  forecast={r['forecast']} "
              f"baseline={r['baseline']}")
    hs = doc["hazard_summary"]
    print(f"HAZARD  {hs['n_measured']}/{hs['n_sleeves']} sleeve(s) measured over "
          f"{hs['horizon_days']:g}d  breaking={hs['breaking']}  at_risk={hs['at_risk']}")
    ranked = sorted(((k, v) for k, v in doc["hazard_by_sleeve"].items()
                     if v.get("hazard") is not None), key=lambda kv: -kv[1]["hazard"])
    for name, h in ranked[:10]:
        print(f"  {name[:34]:34s} P={h['hazard']:.1%} {h['verdict']:9s} "
              f"channels={h['n_measured']}/{len(ph.HAZARD_COMPONENTS)} "
              f"led by {h.get('leading_channel')}")
    for w in doc["degraded"]:
        print(f"  DEGRADED: {w}")
    if not a.no_write:
        print(f"written: {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
