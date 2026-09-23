"""Every publicly described hedge-fund mechanism, as a deterministic hypothesis card with a grade.

WHAT THIS IS. A corpus of the mechanisms Bridgewater, AQR, Man AHL, Cubist, Citadel and
Renaissance have described in public -- statements, papers, interviews, testimony -- plus the
lower-grade social claims about them, each written down as something this desk can TEST: a
family the desk has, parameters, the instruments it applies to, the economic argument, and an
evidence grade. Cards whose family exists are donated to the miner contract as EXACT_RECIPE rows
and face the ten gates. Cards whose family does not exist yet go to the deepening queue with the
source text, so the research brains work them rather than forget them.

WHAT THE GRADE MEANS, and what it does NOT. A is the firm's own words; B is reputable reporting
or book-derived; C is social media, ex-employee hearsay, or inference. The grade is carried on the
card and on the candidate. It changes NOTHING about how the gauntlet treats the cell -- a C-grade
rumour that certifies is certified, an A-grade statement that fails is failed. The grade exists
so a later reader knows what kind of prior produced the hypothesis, which is the difference
between a research record and a pile of guesses.

NOT A SECOND DOOR. Cards are miner rows. `miner_candidate_compiler` admits or routes them by the
same rules as every other source, and `hypothesis_graph` records each with the fund and the
claim as its parent, so the lineage from a public statement to a certificate (or a grave) is
explicit.

WHAT IS DELIBERATELY NOT HERE. Anything requiring data the desk has no route to -- fundamental
equity data, rates curves for countries whose bonds Fusion does not offer, order-book depth --
is a card with `blocked_on` filled in, routed to the prospector rather than pretended.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

SOURCE = "fund_playbook"
OUT = BASE / "data" / "intelligence" / SOURCE
REPORT = BASE / "reports" / "FUND_PLAYBOOK.json"

A, B, C = "A", "B", "C"

#: Each card: who, what they said (paraphrased), the grade, and how this desk states it.
#: `family`/`params`/`symbols` make it executable; `blocked_on` names the missing input instead.
CARDS: list[dict] = [
    # ---------------------------------------------------------------- Renaissance
    {"fund": "Renaissance", "grade": A, "claim": "predictions profitable only slightly more often "
     "than not; volume of recommendations does the work (Senate statement)",
     "family": "ensemble", "note": "the weak-signal compiler IS this card; nothing to donate here",
     "symbols": [], "params": {}},
    {"fund": "Renaissance", "grade": A, "claim": "stock book approximately balanced long/short, "
     "buying recent losers and selling recent winners (Simons, 2008 testimony)",
     "family": "cross_asset_residual", "symbols": ["Apple", "Microsoft", "Amazon", "Nvidia",
     "Alphabet-A", "Meta", "Tesla", "JPMorganChase", "ExxonMobil", "Berkshire"],
     "params": {"factor_symbols": ["US500"], "lookback": 120, "beta_win": 120, "entry_z": 2.0,
                "ttl_bars": 48, "side_mode": "revert"},
     "why": "market-neutral residual reversion in single names: the residual to the index is "
            "the idiosyncratic return, and its mean reversion is the stated mechanism"},
    {"fund": "Renaissance", "grade": B, "claim": "an early effect came from the 15-minute gap "
     "between S&P options and futures closing times (Zuckerman)",
     "family": "clock_transition", "symbols": ["US500", "NAS100", "US30"],
     "params": {"label": "cash_equity_close", "stamp_hour": None, "mode": "fade", "side": 1,
                "lead_bars": 1, "hold_bars": 2},
     "why": "venue-timing mismatch around the cash close; plumbing_miner resolves the stamp hour"},
    {"fund": "Renaissance", "grade": B, "claim": "five-minute bars became important for finding "
     "nonrandom effects (Laufer, book-derived)", "family": None, "symbols": [],
     "blocked_on": "M5 bars for book symbols", "why": "intraday temporal-sequence mining"},
    {"fund": "Renaissance", "grade": C, "claim": "win rate ~50.75% (attributed to Mercer, "
     "social)", "family": None, "symbols": [], "params": {},
     "note": "a calibration target for the ensemble's hit rate, not a hypothesis"},
    # ---------------------------------------------------------------- Bridgewater
    {"fund": "Bridgewater", "grade": A, "claim": "trade growth/inflation SURPRISES relative to "
     "what is discounted, not levels", "family": "event_reaction",
     "symbols": ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "US500"],
     "params": {"input_source": "ff_calendar_vintage"},
     "blocked_on": "calendar ACTUAL prints (surprise = actual - forecast is uncomputable)",
     "why": "the desk's calendar carries forecast and previous but no actual"},
    {"fund": "Bridgewater", "grade": A, "claim": "cross-country divergence in policy and "
     "conditions creates relative-value FX/rates trades",
     "family": "cross_asset_residual", "symbols": ["EURGBP", "EURJPY", "GBPJPY", "AUDNZD",
     "EURCHF", "AUDCAD", "NZDCAD", "EURAUD", "GBPAUD"],
     "params": {"factor_symbols": ["USDX"], "lookback": 240, "beta_win": 240, "entry_z": 2.0,
                "ttl_bars": 72, "side_mode": "revert"},
     "why": "strip the dollar; the residual of a cross is the two countries' relative state"},
    {"fund": "Bridgewater", "grade": A, "claim": "real-yield / gold relationship; asset-yield "
     "vs cash-rate equilibrium gap", "family": "cross_asset_residual",
     "symbols": ["XAUUSD", "XAGUSD"],
     "params": {"factor_symbols": ["USDX", "UST10Y"], "lookback": 240, "beta_win": 240,
                "entry_z": 2.0, "ttl_bars": 72, "side_mode": "revert"},
     "why": "gold as a zero-coupon real asset priced off the real rate it forgoes"},
    {"fund": "Bridgewater", "grade": A, "claim": "risk-balance exposures so no one macro factor "
     "dominates", "family": None, "symbols": [], "params": {},
     "note": "this is the allocator's factor_k_eff bound (PR #10), already enforced"},
    {"fund": "Bridgewater", "grade": B, "claim": "policy -> liquidity/credit -> spending -> "
     "inflation/growth -> rates -> FX transmission chain", "family": "macro_conditional",
     "symbols": ["EURUSD", "USDJPY", "GBPUSD", "AUDUSD"],
     "params": {"input_source": "fred:macro", "transform": "trailing_pct_rank",
                "publication_lag_d": 45},
     "why": "condition FX direction on the macro impulse's percentile rank, lagged for publication"},
    {"fund": "Bridgewater", "grade": B, "claim": "real-exchange-rate disequilibrium mean-reverts "
     "over long horizons", "family": None, "symbols": ["EURUSD", "GBPUSD", "USDJPY"],
     "blocked_on": "CPI series per country (FRED/ECB/ONS) to build real exchange rates",
     "why": "PPP deviation as a slow-reverting state"},
    # ---------------------------------------------------------------- AQR
    {"fund": "AQR", "grade": A, "claim": "time-series momentum across asset classes "
     "(Moskowitz-Ooi-Pedersen)", "family": "multi_speed_trend",
     "symbols": ["XAUUSD", "EURUSD", "USDJPY", "GBPUSD", "US500", "NAS100", "XBRUSD", "AUDUSD"],
     "params": {"speeds": [10, 21, 63, 126, 252], "hold_days": 5, "min_agreement": 0.6},
     "why": "sign of trailing return, vol-scaled, ensemble of speeds"},
    {"fund": "AQR", "grade": A, "claim": "carry across asset classes", "family": "carry",
     "symbols": ["AUDJPY", "NZDJPY", "USDTRY", "USDZAR", "USDMXN", "EURTRY", "GBPJPY"],
     "params": {"input_symbol": None},
     "why": "broker swap differential is a directly measured carry premium"},
    {"fund": "AQR", "grade": A, "claim": "naive factor timing deteriorates after lags and costs",
     "family": None, "symbols": [], "params": {},
     "note": "a NEGATIVE card: multi_speed_trend does not time itself, by design"},
    {"fund": "AQR", "grade": A, "claim": "betting-against-beta / defensive: low-beta names "
     "outperform per unit of risk", "family": "cross_asset_residual",
     "symbols": ["JohnsonJohnson", "ProcterGamble", "CocaCola", "Walmart", "PepsiCo"],
     "params": {"factor_symbols": ["US500"], "lookback": 240, "beta_win": 240, "entry_z": 1.5,
                "ttl_bars": 120, "side_mode": "continue"},
     "why": "residual continuation in low-beta names: the defensive premium as a residual drift"},
    # ---------------------------------------------------------------- Man AHL
    {"fund": "Man AHL", "grade": A, "claim": "multi-speed trend; fastest speeds carry the crisis "
     "alpha", "family": "multi_speed_trend",
     "symbols": ["US500", "NAS100", "GER40", "JPN225", "XAUUSD", "USDJPY"],
     "params": {"speeds": [5, 10, 21, 63], "hold_days": 3, "min_agreement": 0.5,
                "crisis_only": True},
     "why": "enter only at the turn where the fast speed disagrees with the slow: crisis alpha"},
    {"fund": "Man AHL", "grade": A, "claim": "breadth: trade hundreds of markets", "family": None,
     "symbols": [], "params": {}, "note": "the 251-instrument universe and economic_drivers map"},
    # ---------------------------------------------------------------- Cubist / Citadel
    {"fund": "Cubist", "grade": A, "claim": "mid-frequency anomalies from price-volume + "
     "order-book + alternative data, feature-combined", "family": "orderflow_imbalance",
     "symbols": ["XAUUSD", "EURUSD", "USDJPY"], "params": {"input_source": "fusion_tick_tape"},
     "why": "tick-derived flow imbalance as the price-volume anomaly the desk can measure"},
    {"fund": "Citadel", "grade": A, "claim": "observe -> precise hypothesis -> test -> scale "
     "only on evidence", "family": None, "symbols": [], "params": {},
     "note": "the ten-gate gauntlet and the promoter's forward evidence are this process"},
    # ---------------------------------------------------------------- Social / unverified
    {"fund": "social", "grade": C, "claim": "Medallion uses hidden Markov models / regime "
     "switching as the core", "family": "regime_transition",
     "symbols": ["XAUUSD", "EURUSD", "USDJPY"],
     "params": {"window": 750, "refit_days": 250, "horizon_days": 1, "entry_p_leave": 0.25,
                "min_age": 5, "side_mode": "exhaustion"},
     "why": "if the claim has any content, it is that regime ENDINGS are tradeable"},
    {"fund": "social", "grade": C, "claim": "leverage ~12.5x, sometimes 20x", "family": None,
     "symbols": [], "params": {}, "note": "not a hypothesis; never a sizing target"},
]


def executable(card: dict) -> bool:
    return bool(card.get("family")) and not card.get("blocked_on") and bool(card.get("symbols"))


def rows() -> tuple[list[dict], list[dict], list[dict]]:
    """(donatable rows, deepening rows, informational cards)."""
    try:
        from mt5desk.families_orthogonal import ORTHOGONAL_FAMILIES
        known = set(ORTHOGONAL_FAMILIES) | {"session_range_breakout", "discovered"}
    except Exception:                                            # noqa: BLE001
        known = set()
    donate, deepen, info = [], [], []
    for c in CARDS:
        base = {"source": SOURCE, "kind": "fund_claim", "fund": c["fund"],
                "evidence_grade": c["grade"], "title": f"{c['fund']} [{c['grade']}]: {c['claim'][:90]}",
                "text": c["claim"], "url": "", "mechanism": c.get("why") or c.get("note") or "",
                "found_at": datetime.now(tz=UTC).isoformat()}
        if not c.get("family"):
            info.append({**base, "note": c.get("note"), "blocked_on": c.get("blocked_on")})
            continue
        if c.get("blocked_on"):
            deepen.append({**base, "family": c["family"], "symbols": c["symbols"],
                           "params": c.get("params") or {}, "blocked_on": c["blocked_on"]})
            continue
        if c["family"] not in known:
            deepen.append({**base, "family": c["family"], "symbols": c["symbols"],
                           "params": c.get("params") or {},
                           "blocked_on": f"family {c['family']} not registered here"})
            continue
        for sym in c["symbols"]:
            params = dict(c.get("params") or {})
            if c["family"] == "carry":
                params["input_symbol"] = sym
            if c["family"] == "clock_transition" and params.get("stamp_hour") is None:
                # The plumbing miner owns the offset; a card cannot know the stamp hour. It is
                # routed to deepening with the label so the miner's own sweep covers it.
                deepen.append({**base, "family": c["family"], "symbols": [sym], "params": params,
                               "blocked_on": "stamp hour resolved by plumbing_miner, not by a card"})
                break
            donate.append({**base, "symbol": sym, "symbols": [sym], "family": c["family"],
                           "params": params})
    return donate, deepen, info


def run() -> dict:
    donate, deepen, info = rows()
    try:
        from libs.data.pit import stamp as _pit_stamp
        donate = [_pit_stamp(r, SOURCE) for r in donate]
        deepen = [_pit_stamp(r, SOURCE) for r in deepen]
    except Exception:                                            # noqa: BLE001
        pass
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M")
    path = OUT / f"discoveries_{stamp}.json"
    path.write_text(json.dumps({"source": SOURCE, "generated_at": datetime.now(tz=UTC).isoformat(),
                                "discoveries": donate + deepen}, indent=1, default=str), "utf-8")
    try:
        from libs.research.hypothesis_graph import BORN, Graph, Node
        g = Graph()
        for r in donate:
            g.append(Node(symbol=r["symbol"], family=r["family"], params=r["params"],
                          source=f"{SOURCE}:{r['fund']}:{r['evidence_grade']}",
                          parent=f"{r['fund']}|{r['text'][:60]}", fate=BORN,
                          why=r["mechanism"][:200]))
    except Exception:                                            # noqa: BLE001
        pass
    doc = {"generated_utc": datetime.now(tz=UTC).isoformat(), "cards": len(CARDS),
           "donated_rows": len(donate), "deepening_rows": len(deepen), "informational": len(info),
           "by_grade": {g: sum(1 for c in CARDS if c["grade"] == g) for g in (A, B, C)},
           "by_fund": {f: sum(1 for c in CARDS if c["fund"] == f) for f in
                       sorted({c["fund"] for c in CARDS})},
           "blocked": [{"fund": r["fund"], "claim": r["text"][:80], "on": r["blocked_on"]}
                       for r in deepen], "donated_to": str(path)}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    return doc


def main() -> int:
    argparse.ArgumentParser().parse_args()
    d = run()
    print(f"FUND PLAYBOOK  {d['cards']} cards -> {d['donated_rows']} executable rows, "
          f"{d['deepening_rows']} to deepening, {d['informational']} informational")
    print(f"  grades {d['by_grade']}  funds {d['by_fund']}")
    for b in d["blocked"]:
        print(f"  BLOCKED {b['fund']:12s} {b['claim'][:60]:60s} on: {b['on']}")
    print(f"donated: {d['donated_to']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
