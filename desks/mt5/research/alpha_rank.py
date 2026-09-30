"""THE NORTH STAR: EFFECTIVE INDEPENDENT ALPHA RANK, over every CERTIFIED edge.

    "Effective independent breadth: independence graph from PnL corr, tail corr, factor exposure,
     shared feature ancestry, overlapping timestamps, same causal mechanism, common execution
     exposure, conditional regime corr. North-star metric = effective independent alpha rank."
                                                                  -- the principal, 2026-09-29

WHY A FOURTH BREADTH ARTIFACT. `alpha_breadth` (EFFECTIVE_BREADTH.json) measures the LIVE BOOK,
`rank_recovery` measures how evenly the desk's CANDIDATE output is spread over producers, and
`alpha_genome` clusters certificates by structure alone. None of them answers the question the
research machine exists for: of everything the desk has CERTIFIED, how many genuinely independent
sources of return is that? A certificate that has not reached a clock yet is still either new
breadth or a re-finding, and research must be credited for the first and not the second.

WHAT IT READS (never writes any of it):

    reports/UNIVERSAL_SURVIVORS.json      the certificate truth (fallback: the canon copy)
    data/universe/<SYM>_H1.parquet        daily instrument returns -> the P&L PROXY, tail and
                                          regime channels (via alpha_breadth._daily_panel)
    reports/shadow/ledger_*.json          realised daily P&L where a certificate has a clock --
                                          realised beats the proxy wherever both exist
    data/universe/universe.json           asset classes, for the execution channel
    reports/EFFECTIVE_BREADTH.json        the live book's headline, published BESIDE this one

WHAT IT WRITES:

    reports/ALPHA_RANK.json               schema-versioned; the north star, each channel's own
                                          rank and coverage, per-certificate marginal rank,
                                          same-bet clusters, and per-PRODUCER independent-alpha
                                          yield (read by factory_contracts -> the research budget)
    data/alpha_rank.jsonl                 one row per run: the series the principal wants raised

The combination rule and every channel's definition live in `libs/research/independence_graph.py`
(pure, typed, tested). NOTHING HERE SIZES, GATES OR PROMOTES.

    python desks/mt5/research/alpha_rank.py [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import independence_graph as ig  # noqa: E402

SCHEMA_VERSION = "alpha_rank/1"
SURVIVORS = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"
CANON = DESK / "data" / "UNIVERSAL_SURVIVORS.canon.json"
UNIVERSE_JSON = DESK / "data" / "universe" / "universe.json"
LIVE_BREADTH = DESK / "reports" / "EFFECTIVE_BREADTH.json"
OUT = DESK / "reports" / "ALPHA_RANK.json"
HISTORY = DESK / "data" / "alpha_rank.jsonl"
UNMEASURED = "UNMEASURED"

#: Family -> mechanism class, borrowed from the genome so the two artifacts speak one vocabulary.
try:
    from alpha_genome import MECHANISM_CLASS  # type: ignore[import-not-found]
except Exception:                                              # pragma: no cover - import env
    MECHANISM_CLASS = {}


def _read(p: Path) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def certificates() -> tuple[dict[str, dict[str, Any]], str]:
    """(key -> certificate, which file answered). The published truth first, the canon second."""
    for p in (SURVIVORS, CANON):
        doc = _read(p)
        surv = doc.get("survivors") if isinstance(doc, dict) else None
        if isinstance(surv, dict) and surv:
            return {str(k): v for k, v in surv.items() if isinstance(v, dict)}, p.name
    return {}, UNMEASURED


def _asset_classes() -> dict[str, str]:
    doc = _read(UNIVERSE_JSON)
    rows: Any = doc.get("symbols") if isinstance(doc, dict) else doc
    out: dict[str, str] = {}
    if isinstance(rows, dict):
        rows = [dict(v, name=k) for k, v in rows.items() if isinstance(v, dict)]
    for r in rows if isinstance(rows, list) else []:
        if isinstance(r, dict):
            name = str(r.get("name") or r.get("symbol") or "").upper()
            cls = str(r.get("asset_class") or r.get("path") or "")
            if name:
                out[name] = cls
    return out


def _side(v: Any) -> int:
    s = str(v or "").upper()
    return 1 if s in ("LONG", "BUY", "1", "+1") else (-1 if s in ("SHORT", "SELL", "-1") else 0)


def to_edges(certs: dict[str, dict[str, Any]],
             classes: dict[str, str] | None = None) -> list[ig.Edge]:
    """Certificates -> typed edges. The producer is the certificate's own `hunt`/`generator`
    stamp -- the same tokens `productivity_census` joins on -- and nothing is guessed."""
    try:
        from libs.research.strategy_artifact import feature_ids_of
    except Exception:                                          # pragma: no cover
        def feature_ids_of(params: dict[str, Any] | None) -> list[str]:
            return sorted(str(k) for k in (params or {}))
    classes = classes or {}
    out: list[ig.Edge] = []
    for key, c in sorted(certs.items()):
        spec = c.get("shadow_spec") if isinstance(c.get("shadow_spec"), dict) else {}
        sym = str(c.get("sym") or spec.get("symbol") or "").upper()
        fam = str(spec.get("family") or c.get("family") or "")
        params = spec.get("params") if isinstance(spec.get("params"), dict) else (
            c.get("params") if isinstance(c.get("params"), dict) else {})
        producer = c.get("generator") or c.get("origin") or c.get("hunt")
        out.append(ig.Edge(
            key=key, symbol=sym, family=fam,
            mechanism=str(MECHANISM_CLASS.get(fam, "UNCLASSIFIED")),
            side=_side(spec.get("side") or c.get("side")),
            session=str(spec.get("selector") or c.get("selector") or "any"),
            asset_class=classes.get(sym, ""),
            feature_ids=frozenset(feature_ids_of(params)),
            producer=str(producer) if producer else None))
    return out


def _realised(edges: list[ig.Edge]) -> tuple[dict[str, dict[str, float]], dict[str, str]]:
    """Realised daily P&L per certificate, joined to a shadow ledger ONLY when the ledger's name
    carries the certificate's symbol and its session selector. Anything looser would be the
    fuzzy sleeve-name join the principal named as a defect; a certificate without such a ledger
    falls back to the proxy and the report says which basis each pair used."""
    try:
        from alpha_breadth import daily_sleeve_returns  # type: ignore[import-not-found]
        series = daily_sleeve_returns()
    except Exception:
        return {}, {}
    out: dict[str, dict[str, float]] = {}
    joined: dict[str, str] = {}
    for e in edges:
        want_sym, want_sel = e.symbol.lower(), e.session.lower()
        hits = [s for s in series
                if want_sym and want_sym in s.lower() and want_sel != "any"
                and want_sel in s.lower()]
        if len(hits) == 1:
            out[e.key] = series[hits[0]]
            joined[e.key] = hits[0]
    return out, joined


def _proxy(symbols: list[str]) -> tuple[dict[str, list[float]], dict[str, str], list[float]]:
    try:
        from alpha_breadth import _daily_panel  # type: ignore[import-not-found]
        panel, dropped = _daily_panel(sorted(set(symbols)))
    except Exception as exc:
        return {}, {"panel": f"{type(exc).__name__}: {exc}"}, []
    regime: list[float] = []
    if len(panel) >= 2:
        try:
            from libs.research.effective_breadth import lagged_vol_regime
            regime = [float(x) for x in lagged_vol_regime(panel)]
        except Exception:
            regime = []
    return panel, dropped, regime


def build() -> dict[str, Any]:
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    certs, source = certificates()
    edges = to_edges(certs, _asset_classes())
    live = _read(LIVE_BREADTH)
    live_head = ((live or {}).get("effective") or {}).get("effective_breadth") \
        if isinstance(live, dict) else None
    base: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION, "graph_schema": ig.SCHEMA_VERSION, "at": now,
        "certificate_source": source, "n_certificates": len(edges),
        "live_book_effective_breadth": live_head,
        "channels_declared": list(ig.CHANNELS),
    }
    if len(edges) < 2:
        return {**base, "status": UNMEASURED, "north_star": None,
                "why": (f"{len(edges)} certificate(s) readable from {source}; an independence "
                        "rank needs at least two")}
    realised, joined = _realised(edges)
    panel, dropped, regime = _proxy([e.symbol for e in edges])
    g = ig.build_graph(edges, realised, panel, regime or None)
    rank = g.rank()
    marginal = g.marginal()
    clusters = g.clusters()
    yld = ig.producer_yield(edges, marginal)
    no_bars = sorted({e.symbol for e in edges if e.symbol not in panel})
    by_key = {e.key: e for e in edges}
    return {
        **base,
        "status": "MEASURED",
        "north_star": {
            "effective_independent_alpha_rank": round(rank, 4) if rank is not None else None,
            "n_certified": len(edges),
            "rank_per_certificate": (round(rank / len(edges), 4) if rank else None),
            "n_same_bet_clusters": len(clusters),
            "rule": ("n^2 / sum_ij D_ij^2 over the conservative combined dependence matrix; "
                     "n independent certificates give n, n copies of one give 1"),
        },
        "channels": {c: g.channel_rank(c) for c in ig.CHANNELS},
        "pnl_basis_pairs": g.pnl_basis,
        "n_pairs_assumed_dependent": g.n_pairs_unmeasured,
        "realised_joins": joined,
        "instruments_without_bars": no_bars,
        "instruments_dropped_from_panel": dropped,
        "clusters": [{"size": len(c), "members": c,
                      "families": sorted({by_key[k].family for k in c}),
                      "symbols": sorted({by_key[k].symbol for k in c})}
                     for c in clusters if len(c) > 1][:25],
        "marginal_rank": dict(sorted(marginal.items(), key=lambda kv: -kv[1])),
        "producer_independent_alpha": dict(sorted(yld.items(), key=lambda kv: -kv[1])),
        "unattributed_certificates": sorted(e.key for e in edges if not e.producer),
        "combination": ("statistical = max(pnl_corr, tail_corr, regime_corr); structural = "
                        "mean(factor_exposure, feature_ancestry, timestamp_overlap, "
                        "same_mechanism, execution_exposure); D = max(statistical, structural); "
                        "a pair with nothing measured is D = 1"),
        "limitations": [
            "pnl_corr is the INSTRUMENT PROXY (signed daily instrument return) wherever no "
            "shadow ledger joins a certificate exactly; it ignores the session/condition filter, "
            "which OVERSTATES dependence -- the conservative direction",
            "a certificate on an instrument with no local bars has no statistical channel; its "
            "structural channels still bind",
        ],
        "consumers": ["desks/mt5/research/factory_contracts.py (independent_alpha_yield)",
                      "data/alpha_rank.jsonl (the north-star series)"],
        "boundary": "measures only: nothing here sizes, gates, promotes or admits",
    }


def _append_history(doc: dict[str, Any]) -> None:
    ns = doc.get("north_star") or {}
    row = {"at": doc["at"], "schema_version": SCHEMA_VERSION, "status": doc.get("status"),
           "n_certified": doc.get("n_certificates"),
           "effective_independent_alpha_rank": ns.get("effective_independent_alpha_rank"),
           "live_book_effective_breadth": doc.get("live_book_effective_breadth")}
    try:
        HISTORY.parent.mkdir(parents=True, exist_ok=True)
        with HISTORY.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
    except OSError:
        pass


def write(doc: dict[str, Any], path: Path | None = None) -> Path:
    p = path or OUT
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, p)
    return p


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    doc = build()
    ns = doc.get("north_star") or {}
    print(f"alpha rank: {doc['status']}  {doc['n_certificates']} certificate(s) from "
          f"{doc['certificate_source']} -> effective independent alpha rank "
          f"{ns.get('effective_independent_alpha_rank')} (live book "
          f"{doc.get('live_book_effective_breadth')})")
    for c, v in (doc.get("channels") or {}).items():
        print(f"   {c:<20} {v.get('status'):<10} rank={v.get('rank')} cov={v.get('coverage')}")
    for p, y in list((doc.get("producer_independent_alpha") or {}).items())[:8]:
        print(f"   producer {p:<30} +{y}")
    if not a.dry_run:
        print(f"-> {write(doc)}")
        _append_history(doc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
