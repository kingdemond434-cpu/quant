"""THE PORTFOLIO BOUNTY SYSTEM (Tier-5 mandate 90 / 118 PORTFOLIO_BOUNTY): the allocator's
missing payoff shapes and regimes, published as MissingPayoffRequest rows into the registry.

`portfolio_gap` (daily) turns unfilled HEAT into missions. Nothing turned the SHAPE of what the
book lacks into research demand: the crisis cluster the drawdown factory reports empty, the regime
buckets no sleeve has traded, the factor the exposure decomposition shows the book concentrated
on, the asset classes with no live sleeve, the bands of the day with no heat, the pairs whose tail
dependence is hidden. Each of those is a payoff the allocator cannot buy, and each becomes a
bounty here, hourly, from the artifacts that already measure it:

    drawdown_positive     DRAWDOWN_ALPHA (crisis_cluster_empty, candidates) and the
                          DRAWDOWN_ALPHA_MINER windows: need a payoff inside the book's drawdowns
    regime_uncovered      REGIME_COVERAGE.uncovered: need an edge in a state the book never trades
    factor_concentration  EXPOSURE_DECOMPOSITION.book: need a low-<factor>-beta edge
    asset_class_absent    universe.json asset classes with no LIVE sleeve
    session_dark          session_capital.dark_bands: need an edge in an empty band of the day
    heat_shortfall        pf_allocation.heat.shortfall > 0: need positive marginal dE[log W]
    tail_dependence       ORTHOGONALITY.hidden_dependence_pairs: need tail-independent payers

Every bounty is a registry memory (category portfolio_bounty, kind missing_payoff, upserted on
its stable id), a PORTFOLIO_BOUNTY event, and a deepening-queue mission addressed to the world,
country, data, math, physics and sandbox miners. `research_auction` reads the open bounties and
raises the bids of the departments that can serve them. A bounty funds nothing and gates nothing.
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
REPO = BASE.parents[1]
for _p in (str(REPO), str(BASE / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

R = BASE / "reports"
OUT = R / "PORTFOLIO_BOUNTY.json"
ALLOC = R / "pf_allocation.json"
BREADTH = R / "EFFECTIVE_BREADTH.json"
EXPOSURE = R / "EXPOSURE_DECOMPOSITION.json"
REGIMES = R / "REGIME_COVERAGE.json"
DRAWDOWN = R / "DRAWDOWN_ALPHA.json"
DD_MINER = R / "DRAWDOWN_ALPHA_MINER.json"
ORTHO = R / "ORTHOGONALITY.json"
SESSION = R / "session_capital.json"
SLEEVES = BASE / "data" / "sleeves.json"
UNIVERSE = BASE / "data" / "universe" / "universe.json"
MAX_PER_KIND = 6
FACTOR_CONCENTRATION = 0.5

#: which research departments / miner families a bounty kind is addressed to.
TARGETS: dict[str, tuple[str, ...]] = {
    "drawdown_positive": ("discovery", "macro", "mathlab", "intel", "validate"),
    "regime_uncovered": ("discovery", "macro", "intel"),
    "factor_concentration": ("discovery", "macro", "intel", "regions"),
    "asset_class_absent": ("intel", "regions", "data", "discovery"),
    "session_dark": ("discovery", "regions", "japan", "intel"),
    "heat_shortfall": ("discovery", "validate", "forward"),
    "tail_dependence": ("mathlab", "validate", "discovery"),
}


def _lst(v: Any) -> list[Any]:
    return v if isinstance(v, list) else []


def _dct(v: Any) -> dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _read(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text("utf-8"))
        return doc if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        return {}


def _bounty(kind: str, key: str, need: str, evidence: dict[str, Any],
            priority: int) -> dict[str, Any]:
    return {"bounty_id": f"bounty:{kind}:{key}"[:160], "kind": kind, "need": need,
            "evidence": evidence, "targets": list(TARGETS.get(kind, ("discovery",))),
            "priority": priority, "status": "open"}


def bounties(alloc: dict[str, Any], exposure: dict[str, Any], regimes: dict[str, Any],
             drawdown: dict[str, Any], dd_miner: dict[str, Any], ortho: dict[str, Any],
             session: dict[str, Any], sleeves: dict[str, Any],
             universe: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    out: list[dict[str, Any]] = []
    unmeasured: list[str] = []

    # 1. a payoff inside the book's own drawdowns
    if drawdown:
        cands = drawdown.get("candidates") or []
        if bool(drawdown.get("crisis_cluster_empty")) or not cands:
            windows = _dct(dd_miner.get("windows"))
            wins = [f"{w['start']}..{w['end']} ({w['depth_r']}R)" for b in ("live", "forward")
                    for w in _lst(windows.get(b))[:2]]
            out.append(_bounty("drawdown_positive", "book",
                               "need a payoff that is POSITIVE inside the book's own drawdown "
                               "windows (crisis convexity / drawdown alpha)",
                               {"crisis_cluster_empty": drawdown.get("crisis_cluster_empty"),
                                "n_candidates_daily": len(cands), "windows": wins,
                                "miner_candidates": len(dd_miner.get("candidates") or [])}, 1))
    else:
        unmeasured.append("DRAWDOWN_ALPHA.json absent")

    # 2. regimes the book never trades
    unc = _lst(regimes.get("uncovered")) if isinstance(regimes.get("uncovered"), list) else None
    if unc is None:
        unmeasured.append("REGIME_COVERAGE.uncovered absent")
    else:
        for bucket in [str(b) for b in unc][:MAX_PER_KIND]:
            out.append(_bounty("regime_uncovered", bucket,
                               f"need an edge that pays in the state {bucket} (no sleeve has "
                               f"traded it)", {"n_uncovered": regimes.get("n_uncovered")}, 2))

    # 3. factor concentration -> low-<factor>-beta demand
    book = _dct(exposure.get("book")) if isinstance(exposure.get("book"), dict) else None
    if book is None:
        unmeasured.append("EXPOSURE_DECOMPOSITION.book absent")
    else:
        loads = {k: abs(float(v)) for k, v in book.items() if isinstance(v, (int, float))}
        total = sum(loads.values())
        if total > 0:
            top, share = max(loads.items(), key=lambda kv: kv[1])
            share = share / total
            if share >= FACTOR_CONCENTRATION:
                out.append(_bounty("factor_concentration", top,
                                   f"need a low-{top}-beta edge: {share:.0%} of the book's "
                                   f"absolute factor exposure sits on {top}",
                                   {"factor": top, "share": round(share, 4),
                                    "n_eff_factor_bets": exposure.get("n_eff_factor_bets")}, 2))

    # 4. asset classes with no live sleeve
    rows = _lst(sleeves.get("sleeves"))
    live_syms = {str(r.get("symbol")) for r in rows
                 if isinstance(r, dict) and str(r.get("status")) == "LIVE"}
    classes: dict[str, set[str]] = {}
    for sym, meta in universe.items():
        if isinstance(meta, dict):
            cls = str(meta.get("asset_class") or meta.get("class") or meta.get("sector") or "")
            if cls:
                classes.setdefault(cls, set()).add(str(sym))
    if not classes:
        unmeasured.append("universe.json carries no asset_class field")
    for cls, syms in sorted(classes.items()):
        if not (syms & live_syms):
            out.append(_bounty("asset_class_absent", cls,
                               f"need a {cls} edge: {len(syms)} tradable symbol(s), no LIVE sleeve",
                               {"n_symbols": len(syms), "sample": sorted(syms)[:6]}, 3))

    # 5. bands of the day with no heat
    dark = session.get("dark_bands") if isinstance(session.get("dark_bands"), list) else None
    if dark is None:
        unmeasured.append("session_capital.dark_bands absent")
    else:
        for band in [str(b) for b in dark][:MAX_PER_KIND]:
            out.append(_bounty("session_dark", band,
                               f"need an edge in the {band} UTC band: the book holds no heat there",
                               {"held_heat": session.get("held_heat")}, 3))

    # 6. unfilled heat
    heat = _dct(alloc.get("heat"))
    short = heat.get("shortfall")
    if isinstance(short, (int, float)) and float(short) > 1e-9:
        out.append(_bounty("heat_shortfall", "book",
                           f"need {float(short):.2%} more filled heat: mechanisms with positive "
                           f"marginal dE[log W] against the held book",
                           {"shortfall": short, "target": heat.get("target"),
                            "free_optimum": heat.get("free_optimum")}, 1))
    elif short is None:
        unmeasured.append("pf_allocation.heat.shortfall absent")

    # 7. hidden tail dependence between held payers
    pairs = ortho.get("hidden_dependence_pairs") \
        if isinstance(ortho.get("hidden_dependence_pairs"), list) else None
    if pairs is None:
        unmeasured.append("ORTHOGONALITY.hidden_dependence_pairs absent")
    else:
        for p in pairs[:MAX_PER_KIND]:
            if not isinstance(p, dict):
                continue
            key = f"{p.get('a')}|{p.get('b')}"
            out.append(_bounty("tail_dependence", key,
                               f"need a payer independent in the lower tail of {p.get('a')} and "
                               f"{p.get('b')} (tail lift {p.get('tail_lift')})",
                               {"pearson": p.get("pearson"), "tail_lift": p.get("tail_lift"),
                                "co_drawdown": p.get("co_drawdown")}, 2))
    out.sort(key=lambda b: (int(b["priority"]), b["kind"], b["bounty_id"]))
    return out, unmeasured


def missions(rows: list[dict[str, Any]], at: str) -> list[dict[str, Any]]:
    return [{
        "mission_id": b["bounty_id"], "source": "portfolio_bounty", "kind": "mission",
        "mission_kind": b["kind"], "issued_at": at, "priority": b["priority"], "status": None,
        "title": f"Bounty: {b['need'][:120]}",
        "detail": (f"{b['need']}. Evidence: {json.dumps(b['evidence'], default=str)[:400]}. "
                   f"Addressed to: {', '.join(b['targets'])}. A candidate answering it carries "
                   f"this mission_id; the MT5/Fusion universe only."),
        "consumer": "world/country/data miners, math and physics factory, sandbox scientists",
    } for b in rows]


def build(now: datetime | None = None, **docs: dict[str, Any]) -> dict[str, Any]:
    at = (now or datetime.now(tz=UTC)).isoformat(timespec="seconds")

    def get(name: str, path: Path) -> dict[str, Any]:
        return docs[name] if name in docs else _read(path)

    rows, unmeasured = bounties(get("alloc", ALLOC), get("exposure", EXPOSURE),
                                get("regimes", REGIMES), get("drawdown", DRAWDOWN),
                                get("dd_miner", DD_MINER), get("ortho", ORTHO),
                                get("session", SESSION), get("sleeves", SLEEVES),
                                get("universe", UNIVERSE))
    by_kind: dict[str, int] = {}
    for b in rows:
        by_kind[b["kind"]] = by_kind.get(b["kind"], 0) + 1
    doc: dict[str, Any] = {
        "at": at, "n_open": len(rows), "by_kind": by_kind, "bounties": rows,
        "missions": missions(rows, at), "unmeasured": unmeasured,
        "targets": TARGETS,
        "consumer": ("research_auction (bids of the addressed departments rise), the deepening "
                     "queue (missions), registry memory category portfolio_bounty, events "
                     "PORTFOLIO_BOUNTY"),
        "rule": ("a bounty is the portfolio naming a payoff it cannot buy; it funds nothing, caps "
                 "nothing and gates nothing; an absent input is UNMEASURED and named"),
    }
    doc["headline"] = f"{len(rows)} open bounties {by_kind}; {len(unmeasured)} input(s) unmeasured"
    return doc


def publish(doc: dict[str, Any], out: Path = OUT, write_queue: bool = True) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    notes = doc.setdefault("publish", {})
    try:
        from libs.moat import registry
        for b in doc["bounties"]:
            registry.remember("portfolio_bounty", b["need"], kind="missing_payoff",
                              memory_key=b["bounty_id"],
                              metrics={"kind": b["kind"], "priority": b["priority"],
                                       "targets": b["targets"], "at": doc["at"]},
                              payload=b["evidence"])
        notes["registry_memories"] = len(doc["bounties"])
    except Exception as exc:
        notes["registry"] = f"not written: {type(exc).__name__}: {exc}"
    try:
        from libs.ops.events import emit
        emit("PORTFOLIO_BOUNTY", leg="portfolio_bounty", n=doc["n_open"], by_kind=doc["by_kind"])
        notes["event"] = "PORTFOLIO_BOUNTY"
    except Exception as exc:
        notes["event"] = f"not written: {type(exc).__name__}: {exc}"
    if write_queue and doc.get("missions"):
        try:
            rc = importlib.import_module("regime_coverage")
            rc._merge_into_queue(doc["missions"], source="portfolio_bounty")
            notes["queue_rows"] = len(doc["missions"])
        except Exception as exc:
            notes["queue"] = f"not written: {type(exc).__name__}: {exc}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true", default=True)
    ap.add_argument("--budget-s", type=float, default=300.0)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--no-queue", action="store_true")
    a = ap.parse_args(argv)
    t0 = time.monotonic()
    doc = build()
    doc["elapsed_s"] = round(time.monotonic() - t0, 3)
    doc["budget_s"] = a.budget_s
    publish(doc, a.out, write_queue=not a.no_queue)
    print(f"portfolio bounty: {doc['headline']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
