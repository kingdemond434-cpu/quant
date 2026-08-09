#!/usr/bin/env python3
"""THE OPPORTUNITY BOOKS — the return engines the desk had specified and never built.

ELEVEN BOOKS, EACH ANSWERING A QUESTION THAT HAD NO ANSWER BEFORE TODAY::

    drawdown_rebound        is this 15% fall a forced-deleveraging flush or a repricing?
    capital_recycling       should this winner be kept, trimmed, harvested or rotated?
    strategy_pool           which live algo is degrading, and what on the bench replaces it?
    opportunity_surface     is this validated signal actually tradeable at this book?
    crowding_hazard         is this edge being competed away, before the P&L says so?
    participant_phenotype   which cohort leads price, in which state?
    mechanism_ontology      which candidates are real questions rather than formulas?
    alpha_reserve_bank      if half the live book died today, how much could be replaced?
    portfolio_mc            what happens on the day every strategy loses at once?
    market_breadth          where else can this mechanism meet the state it needs?
    agent_authority         which component may reach which surface, and what does it break?

**EVERY BOOK REPORTS UNMEASURED WHEN ITS INPUT IS ABSENT, AND MOST OF THEM ARE TODAY.** That is
the honest state: this desk has no live positions, no cohort data and no crowding history. The
books exist now so that the day those arrive, nothing has to be remembered and wired -- a
capability wired only when its input appears is a capability wired late.

The mechanism ontology is the exception and it produces real output immediately, because its input
is economic reasoning rather than market data. It is the one book that can work on a
network-denied clone, and its first run says something concrete: 83% of the naive combinatorial
space is refused before it costs anything.

The last section is not a return engine and is here because it must RUN somewhere: agent authority
describes which component may reach which surface. A permission policy that nothing executes is
prose, and prose does not fail a build the morning a grant has drifted.

Reads artifacts, writes one. Trades nothing, sizes nothing, promotes nothing.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.execution.opportunity_surface import BookState, SignalState  # noqa: E402
from libs.execution.opportunity_surface import summarise as execution_summary  # noqa: E402
from libs.ops.agent_authority import AgentGrant, BlastRadius  # noqa: E402
from libs.ops.agent_authority import summarise as authority_summary  # noqa: E402
from libs.portfolio.alpha_reserve_bank import ReserveCandidate  # noqa: E402
from libs.portfolio.alpha_reserve_bank import summarise as reserve_summary  # noqa: E402
from libs.portfolio.capital_recycling import PositionState  # noqa: E402
from libs.portfolio.capital_recycling import summarise as recycling_summary  # noqa: E402
from libs.portfolio.portfolio_monte_carlo import StrategyPath  # noqa: E402
from libs.portfolio.portfolio_monte_carlo import summarise as portfolio_mc_summary  # noqa: E402
from libs.portfolio.strategy_pool import PoolMember  # noqa: E402
from libs.portfolio.strategy_pool import summarise as pool_summary  # noqa: E402
from libs.research.crowding_hazard import CrowdingState  # noqa: E402
from libs.research.crowding_hazard import summarise as crowding_summary  # noqa: E402
from libs.research.drawdown_rebound import DeclineEvent  # noqa: E402
from libs.research.drawdown_rebound import summarise as rebound_summary  # noqa: E402
from libs.research.market_breadth import Expression  # noqa: E402
from libs.research.market_breadth import summarise as breadth_summary  # noqa: E402
from libs.research.mechanism_ontology import summarise as ontology_summary  # noqa: E402
from libs.research.participant_phenotype import CohortObservation  # noqa: E402
from libs.research.participant_phenotype import summarise as phenotype_summary  # noqa: E402

DATA = ROOT / "data"
OUT = DATA / "opportunity_books.json"

DECLINES = DATA / "decline_events.json"
POSITIONS = DATA / "positions.json"
POOL = DATA / "strategy_pool.json"
SIGNALS = DATA / "signal_book_states.json"
CROWDING = DATA / "crowding_states.json"
COHORTS = DATA / "participant_cohorts.json"
RESERVE = DATA / "alpha_reserve_bank.json"
PATHS = DATA / "strategy_paths.json"
BREADTH = DATA / "market_breadth.json"
AUTHORITY = DATA / "agent_authority.json"


def _load(p: Path) -> object | None:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def _absent(artifact: Path, what: str) -> dict[str, object]:
    return {"measured": False, "missing_artifact": _rel(artifact),
            "headline": (f"UNMEASURED -- {_rel(artifact)} is absent. {what}. Absence must never "
                         "resolve to a verdict")}


def _rows(p: Path, key: str) -> list[dict]:
    raw = _load(p)
    rows = raw.get(key) if isinstance(raw, dict) else None
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def rebound_section() -> dict[str, object]:
    rows = _rows(DECLINES, "events")
    if not rows:
        return _absent(DECLINES, "every drawdown is unclassified, so a forced-deleveraging flush "
                                 "and a fundamental repricing look identical")
    events = [DeclineEvent(**{k: v for k, v in r.items()
                              if k in DeclineEvent.__dataclass_fields__}) for r in rows]
    raw = _load(DECLINES)
    hist = (raw or {}).get("history") if isinstance(raw, dict) else None
    history = {str(k): [tuple(x) for x in v] for k, v in (hist or {}).items()}
    return rebound_summary(events, history)          # type: ignore[arg-type]


def recycling_section() -> dict[str, object]:
    rows = _rows(POSITIONS, "positions")
    if not rows:
        return _absent(POSITIONS, "the desk holds nothing, so KEEP/HARVEST/REDEPLOY is not yet a "
                                  "live question and CAPITAL_RECYCLING_ALPHA has no path to score")
    raw = _load(POSITIONS) or {}
    pos = [PositionState(**{k: v for k, v in r.items()
                            if k in PositionState.__dataclass_fields__}) for r in rows]
    return recycling_summary(
        pos,
        reserve_option_value=float(raw.get("reserve_option_value", 0.0)),   # type: ignore[union-attr]
        recycled_nav=tuple(raw.get("recycled_nav", ())),                    # type: ignore[union-attr]
        static_hold_nav=tuple(raw.get("static_hold_nav", ())),              # type: ignore[union-attr]
        reserve_fraction=float(raw.get("reserve_fraction", 0.0)),           # type: ignore[union-attr]
        drawdown=float(raw.get("drawdown", 0.0)))                           # type: ignore[union-attr]


def pool_section() -> dict[str, object]:
    rows = _rows(POOL, "members")
    if not rows:
        return _absent(POOL, "there is no bench, so a degrading live strategy can only be switched "
                             "OFF rather than replaced, and its capital goes idle")
    members = [PoolMember(**{k: v for k, v in r.items()
                             if k in PoolMember.__dataclass_fields__}) for r in rows]
    return pool_summary(members)


def execution_section() -> dict[str, object]:
    rows = _rows(SIGNALS, "signals")
    if not rows:
        return _absent(SIGNALS, "whether any validated signal is tradeable after spread, fill "
                                "hazard and adverse selection is UNMEASURED")
    pairs = []
    for r in rows:
        s = SignalState(**{k: v for k, v in r.items()
                           if k in SignalState.__dataclass_fields__})
        b = BookState(**{k: v for k, v in (r.get("book") or {}).items()
                         if k in BookState.__dataclass_fields__})
        pairs.append((s, b))
    return execution_summary(pairs)


def crowding_section() -> dict[str, object]:
    rows = _rows(CROWDING, "strategies")
    if not rows:
        return _absent(CROWDING, "decay can only be discovered from returns, which means "
                                 "discovering it after a year of funding it")
    states = [CrowdingState(**{k: v for k, v in r.items()
                               if k in CrowdingState.__dataclass_fields__}) for r in rows]
    return crowding_summary(states)


def phenotype_section() -> dict[str, object]:
    rows = _rows(COHORTS, "cohorts")
    if not rows:
        return _absent(COHORTS, "flow is either unmeasured or aggregated into a single 'retail' "
                                "bucket, in which cohorts that behave oppositely cancel")
    obs = [CohortObservation(**{k: v for k, v in r.items()
                                if k in CohortObservation.__dataclass_fields__}) for r in rows]
    return phenotype_summary(obs)


def reserve_section() -> dict[str, object]:
    rows = _rows(RESERVE, "candidates")
    if not rows:
        return _absent(RESERVE, "REPLACEMENT LATENCY is unmeasured -- if half the live book died "
                                "this morning nobody could say how much of it is replaceable, and "
                                "discovery throughput is worth nothing without that number")
    cands = [ReserveCandidate(**{k: v for k, v in r.items()
                                 if k in ReserveCandidate.__dataclass_fields__}) for r in rows]
    return reserve_summary(cands)


def portfolio_mc_section() -> dict[str, object]:
    rows = _rows(PATHS, "paths")
    if not rows:
        return _absent(PATHS, "the joint drawdown is unmeasured. Per-strategy Monte Carlo already "
                              "runs and cannot answer it: independently shuffling each strategy is "
                              "precisely what destroys the co-movement that kills a book")
    paths = [StrategyPath(**{k: (tuple(v) if isinstance(v, list) else v)
                             for k, v in r.items()
                             if k in StrategyPath.__dataclass_fields__}) for r in rows]
    return portfolio_mc_summary(paths)


def breadth_section() -> dict[str, object]:
    rows = _rows(BREADTH, "expressions")
    if not rows:
        return _absent(BREADTH, "whether a validated mechanism could act anywhere it currently "
                                "does not is UNMEASURED, so the desk defaults to another parameter "
                                "on the same five coins -- which adds no independent evidence")
    exprs = [Expression(**{k: v for k, v in r.items()
                           if k in Expression.__dataclass_fields__}) for r in rows]
    raw = _load(BREADTH) or {}
    depth = int(raw.get("depth_hypotheses", 0))                   # type: ignore[union-attr]
    return breadth_summary(exprs, depth_hypotheses=depth)


def authority_section() -> dict[str, object]:
    rows = _rows(AUTHORITY, "agents")
    if not rows:
        return _absent(AUTHORITY, "which component may reach which surface is UNDECLARED. That is "
                                  "an unknown state rather than a safe one, and it is the state in "
                                  "which a model upgrade quietly widens what something may touch")
    grants = []
    for r in rows:
        blast = BlastRadius(**{k: v for k, v in (r.get("blast") or {}).items()
                               if k in BlastRadius.__dataclass_fields__})
        grants.append(AgentGrant(blast=blast, **{k: (tuple(v) if isinstance(v, list) else v)
                                                 for k, v in r.items()
                                                 if k in AgentGrant.__dataclass_fields__
                                                 and k != "blast"}))
    return authority_summary(grants)


def _safe(name: str, fn, artifact: Path) -> dict[str, object]:
    """A malformed input degrades ONE book to UNMEASURED rather than removing the whole report."""
    try:
        return fn()
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError) as e:
        return {"measured": False, "missing_artifact": _rel(artifact),
                "headline": (f"UNMEASURED -- {name}: {_rel(artifact)} is present but MALFORMED "
                             f"({type(e).__name__}: {e}). A book that cannot parse its input knows "
                             "exactly as much as one with no input")}


def build() -> dict[str, object]:
    books = {
        "drawdown_rebound": _safe("drawdown_rebound", rebound_section, DECLINES),
        "capital_recycling": _safe("capital_recycling", recycling_section, POSITIONS),
        "strategy_pool": _safe("strategy_pool", pool_section, POOL),
        "execution_surface": _safe("execution_surface", execution_section, SIGNALS),
        "crowding_hazard": _safe("crowding_hazard", crowding_section, CROWDING),
        "participant_phenotype": _safe("participant_phenotype", phenotype_section, COHORTS),
        "alpha_reserve_bank": _safe("alpha_reserve_bank", reserve_section, RESERVE),
        "portfolio_monte_carlo": _safe("portfolio_monte_carlo", portfolio_mc_section, PATHS),
        "market_breadth": _safe("market_breadth", breadth_section, BREADTH),
        "agent_authority": _safe("agent_authority", authority_section, AUTHORITY),
        # No input file: its input is economic reasoning, so it works on a network-denied clone.
        "mechanism_ontology": ontology_summary(),
    }
    unmeasured = [k for k, v in books.items() if v.get("measured") is False]
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "books": books,
        "unmeasured_books": unmeasured,
        "next_action": (
            f"{len(unmeasured)} of {len(books)} books have no input: {unmeasured}. Each names the "
            "artifact it needs. Most describe a desk with live positions and cannot be filled from "
            "this clone -- but agent_authority is a POLICY declaration rather than market data, so "
            "if it appears above it is unfilled by omission and not by circumstance"
            if unmeasured else "every book has input"),
        "note": ("These are RETURN ENGINES, not research reports: each answers a question that "
                 "decides where capital goes. Most report UNMEASURED today and that is the honest "
                 "state -- the books exist now so that nothing has to be remembered and wired the "
                 "day the inputs arrive. The mechanism ontology is the exception: its input is "
                 "economic reasoning rather than market data, so it produces real output "
                 "immediately."),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()
    rep = build()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(rep, indent=1), "utf-8")
    print("=== OPPORTUNITY BOOKS ===")
    for name, b in rep["books"].items():          # type: ignore[union-attr]
        print(f"  [{name}] {str(b.get('headline', ''))[:150]}")
    print(f"  NEXT: {rep['next_action']}")
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
