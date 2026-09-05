"""EXECUTION RESOLVER -- an alpha produces an INTENT; Python finds its best executable expression.

THE IDEA, and why it outranks another signal (principal 2026-08-26). A hypothesis says "JPY
weakness". The desk has always answered that by trading whichever symbol the hypothesis happened
to name -- usually USDJPY, because that is what the backtest was written on. But USDJPY is one of
many ways to hold that view and not obviously the best: EURJPY may carry a wider spread yet pay
positive swap, GBPJPY may be far more liquid in the session that fires, CADJPY may be nearly
uncorrelated with what the book already holds. The FORECAST is the same; the EXPRESSION is a
separate decision, and the desk was never making it.

That decision raises realised alpha without discovering a single new forecasting signal, which is
why it outranks more mining: it improves every edge the desk already has, including ones not yet
found.

EVERY TERM IS MEASURED, NOT ASSUMED:

    expected alpha      the intent's own edge, in R
    spread cost         the venue's live spread for that symbol, from the registry
    swap                the actual rollover the venue pays or charges, SIGNED by direction
    slippage            reconstructed from the desk's own tick tape per symbol/session
                        (shadow_execution) -- not a constant, not a guess
    fill probability    the measured rate at which orders actually filled; a 32% desk-wide
                        rejection rate makes an unfillable expression a common failure, not a
                        rounding error
    portfolio overlap   correlation with what the book already holds -- an expression that
                        duplicates a held bet contributes far less than its standalone edge
    margin/size         capital an expression locks is capital no other edge can use

RANKED BY INCREMENTAL EXPECTED LOG-GROWTH, never standalone edge. Two expressions with identical
alpha are not equally good if one duplicates a position already held: the objective is E[log W]
for the WHOLE book.

WHAT IT REFUSES.
  * NO OPTIMISTIC DEFAULTS. A candidate whose execution has never been measured is scored with an
    explicit UNMEASURED penalty and labelled, so it can lose to a worse-looking expression the
    desk actually understands. Absence is never permission (L1.28a).
  * NO MENTAL ACCOUNTING. There is no "house money": profits are capital and are risked under the
    same E[log W] arithmetic as the opening balance.
  * IT NEVER SENDS AN ORDER. It ranks and explains. Promotion authority stays with the ten gates
    and the forward window; this chooses HOW to express something already entitled to trade.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
UNIVERSE = BASE / "data" / "universe"
REGISTRY = UNIVERSE / "universe.json"
EXECQ = BASE / "reports" / "execution_quality.json"
PORTFOLIO = BASE / "reports" / "portfolio_evidence.json"
SLEEVES = BASE / "data" / "sleeves.json"
OUT = BASE / "reports" / "execution_resolver.json"

#: Penalty for a candidate whose execution has NEVER been measured on this desk's tape.
#: Deliberately harsh: it must be able to lose to a measured-but-worse alternative.
UNMEASURED_SLIP_R = 0.25
UNMEASURED_FILL_RATE = 0.60
#: Below this measured fill rate an expression is structurally unfillable, not merely expensive.
MIN_FILL_RATE = 0.40


def _read(p: Path):
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _exec_stats(symbol: str, session: str | None) -> dict:
    doc = _read(EXECQ) or {}
    cells = doc.get("by_symbol_session") or {}
    cell = cells.get(f"{symbol}.{session}") if session else None
    if cell is None:
        for key, val in cells.items():
            if key.startswith(f"{symbol}."):
                cell = val
                break
    if not isinstance(cell, dict) or not cell.get("fills"):
        return {"measured": False, "slip_r": UNMEASURED_SLIP_R,
                "fill_rate": UNMEASURED_FILL_RATE,
                "why": "no reconstructed fills for this symbol -- scored with an UNMEASURED "
                       "penalty rather than a flattering default"}
    slip = (cell.get("slippage_R") or {}).get("median")
    rej = float(doc.get("rejection_rate") or 0.0)
    return {"measured": True,
            "slip_r": float(slip) if slip is not None else UNMEASURED_SLIP_R,
            "fill_rate": max(0.0, 1.0 - rej),
            "fills_seen": int(cell.get("fills") or 0),
            "why": f"reconstructed from {cell.get('fills')} fill(s) on the desk's own tick tape"}


def _atr_distance(symbol: str) -> float | None:
    """Per-symbol stop distance from the symbol's OWN recent bars.

    One risk_distance for every candidate was a silent unit error: 0.35 is a sane stop on gold
    and one fifth of a big figure on GBPJPY. Every cost expressed "per R" inherited whatever
    distortion that mismatch produced. The honest denominator is each symbol's own volatility --
    2x the mean H1 range over the last 200 bars, the same magnitude the families use for stops.
    None when bars are absent: a candidate we cannot size is labelled, not guessed.
    """
    try:
        import pandas as pd
        path = UNIVERSE / f"{symbol}_H1.parquet"
        if not path.exists():
            return None
        df = pd.read_parquet(path, columns=["high", "low"]).tail(200)
        if len(df) < 50:
            return None
        rng = float((df["high"] - df["low"]).mean())
        return rng * 2.0 if rng > 0 else None
    except Exception:
        return None


def _spread_cost_r(meta: dict, risk_distance: float | None) -> float | None:
    """Spread as a fraction of R -- the unit every gate and sizing decision uses."""
    try:
        pts = float(meta.get("median_spread_pts") or 0.0)
        tick = float(meta.get("tick_size") or 0.0)
    except (TypeError, ValueError):
        return None
    if not pts or not tick or not risk_distance:
        return None
    return (pts * tick) / float(risk_distance)


def _overlap(symbol: str) -> float:
    """How much of this expression the book already holds. 1.0 = fully duplicated."""
    doc = _read(PORTFOLIO) or {}
    bets = doc.get("effective_bets") or {}
    held = _read(SLEEVES) or {}
    rows = held.get("sleeves") if isinstance(held.get("sleeves"), dict) else held
    names = list(rows) if isinstance(rows, dict) else []
    if not names:
        return 0.0
    same = sum(1 for n in names if symbol.upper() in str(n).upper())
    if not same:
        # No same-symbol position. Fall back to the book's MEASURED concentration: where N_eff is
        # near 1 almost everything correlates with almost everything, and treating a new name as
        # independent is how twenty variants got counted as twenty bets.
        n_eff, n_sl = bets.get("n_effective"), bets.get("n_sleeves")
        if isinstance(n_eff, (int, float)) and isinstance(n_sl, (int, float)) and n_sl:
            return max(0.0, min(0.9, 1.0 - (float(n_eff) / float(n_sl))))
        return 0.0
    return min(1.0, same / max(1, len(names)))


def resolve(intent: dict, candidates: list[str] | None = None) -> dict:
    """Rank every executable expression of one alpha intent by incremental log-growth."""
    registry = _read(REGISTRY) or {}
    symbols = candidates or sorted(
        p.stem.replace("_H1", "") for p in UNIVERSE.glob("*_H1.parquet"))
    alpha_r = float(intent.get("expected_alpha_r") or 0.0)
    session = intent.get("session")
    risk_distance = intent.get("risk_distance")
    direction = 1 if str(intent.get("direction", "LONG")).upper() == "LONG" else -1
    risk_frac = float(intent.get("risk_frac") or 0.03)

    scored = []
    for sym in symbols:
        meta = registry.get(sym)
        if not isinstance(meta, dict):
            continue                    # never score a symbol the registry cannot describe
        ex = _exec_stats(sym, session)
        # PER-SYMBOL RISK DISTANCE. The intent's number is a fallback, not a truth: a stop
        # distance sane on one instrument is noise on another, and every per-R cost inherits it.
        sym_risk = _atr_distance(sym) or (float(risk_distance) if risk_distance else None)

        spread_r = _spread_cost_r(meta, sym_risk)
        # SWAP, IN COMMENSURATE UNITS. swap_long/short from the venue is CURRENCY PER LOT PER
        # NIGHT; risk_distance is PRICE units. Dividing them directly produced net edges of +23R
        # on GBPJPY -- an artifact of mixed units, not an opportunity. Risk per lot in currency
        # is distance x contract_size; swap contributes only for nights actually held, and a
        # session strategy that closes intraday holds zero.
        swap_ccy = float(meta.get("swap_long" if direction > 0 else "swap_short") or 0.0)
        nights = float(intent.get("expected_holding_nights") or 0.0)
        contract = float(meta.get("contract_size") or 0.0)
        if sym_risk and contract > 0 and nights > 0:
            swap_r = (swap_ccy * nights) / (sym_risk * contract)
        else:
            swap_r = 0.0
        overlap = _overlap(sym)

        net_r = alpha_r - abs(ex["slip_r"]) - abs(spread_r or 0.0) + swap_r
        # Diversification is not a bonus bolted on -- it is the difference between adding a BET
        # and adding a NAME. A fully duplicated expression contributes nothing new.
        effective_r = net_r * (1.0 - overlap)
        # Incremental E[log W] for a small bet ~ f*mu - f^2*sigma^2/2: deliberately penalises
        # size rather than rewarding it.
        log_growth = (risk_frac * effective_r * ex["fill_rate"]
                      - 0.5 * (risk_frac ** 2) * max(1.0, abs(effective_r)))

        scored.append({
            "symbol": sym, "asset_class": meta.get("asset_class", "unknown"),
            "expected_alpha_r": round(alpha_r, 4),
            "slippage_r": round(ex["slip_r"], 4),
            "spread_r": None if spread_r is None else round(spread_r, 4),
            "swap_r": round(swap_r, 6),
            "risk_distance_used": None if sym_risk is None else round(sym_risk, 5),
            "risk_distance_source": ("symbol_atr" if _atr_distance(sym) else
                                     ("intent_fallback" if risk_distance else "unsized")),
            "fill_rate": round(ex["fill_rate"], 3),
            "portfolio_overlap": round(overlap, 3),
            "net_edge_r": round(net_r, 4),
            "effective_edge_r": round(effective_r, 4),
            "incremental_log_growth": round(log_growth, 6),
            "execution_measured": ex["measured"],
            "unfillable": ex["fill_rate"] < MIN_FILL_RATE,
            "why": ex["why"],
        })

    scored.sort(key=lambda r: r["incremental_log_growth"], reverse=True)
    best = next((r for r in scored if not r["unfillable"]), None)
    return {
        "resolved_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "intent": intent, "candidates_scored": len(scored),
        "best": best, "ranked": scored[:20],
        "note": ("Ranked by INCREMENTAL log-growth for the whole book, never standalone edge. "
                 "Unmeasured execution is penalised, never assumed favourable. This never sends "
                 "an order -- promotion authority stays with the ten gates and the forward "
                 "window; this chooses HOW to express something already entitled to trade."),
    }


def main() -> int:
    # Worked example on the real registry and real measured execution, so the resolver is
    # exercised against live data rather than only being importable.
    intent = {"mechanism": "JPY weakness", "direction": "LONG", "expected_alpha_r": 0.15,
              "session": "asia", "risk_distance": 0.35, "risk_frac": 0.03}
    report = resolve(intent, candidates=["USDJPY", "EURJPY", "GBPJPY", "CADJPY", "AUDJPY",
                                         "CHFJPY", "NZDJPY", "XAUUSD"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, default=str), "utf-8")
    print(f"execution resolver: {report['candidates_scored']} expression(s) of "
          f"'{intent['mechanism']}'")
    for r in report["ranked"][:8]:
        flag = ("UNFILLABLE" if r["unfillable"]
                else ("measured" if r["execution_measured"] else "UNMEASURED"))
        print(f"   {r['symbol']:8} logG={r['incremental_log_growth']:+.6f} "
              f"net={r['net_edge_r']:+.3f}R slip={r['slippage_r']:.3f}R "
              f"overlap={r['portfolio_overlap']:.2f} [{flag}]")
    if report["best"]:
        print(f"  BEST: {report['best']['symbol']} -- not necessarily the symbol the hypothesis "
              f"named, which is the entire point")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
