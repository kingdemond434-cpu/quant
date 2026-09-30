"""THE REGISTRY'S CELLS, IN THE FILE THE SEALED JUDGE READS.

THE DEFECT THIS CLOSES, traced end to end on the trading box and re-measured 2026-09-24.
`desks/mt5/scripts/external_gauntlet.py` (SEALED, never edited, never imported here) opens exactly
one input in `main()`: `desks/mt5/data/hypotheses/external_survivors.json`. It never opens
`data/alpha_registry.sqlite`. So a cell minted into the canonical research registry -- by
`pack_cells`, by `discovery_compiler`, by `independence_intake`, by any `miner:*` producer calling
`enqueue_candidate` -- had NO PATH TO A JUDGE AT ALL, whatever its score. The single door out of
the database was `moat_candidate_compiler.claim_and_donate`, leasing 276 rows an hour into the
donation intake against 356,087 candidates: 54 days to walk the population once, against a
population that grows faster than that.

WHAT THIS IS. The supported seam, used the way it is meant to be used: this module FEEDS the
judge's input file and does not touch the judge. `merge_hypotheses` is the one writer of that
file and already unions seven producers into it; this is the eighth, reading the registry
directly rather than through a leased trickle. Nothing here judges, scores, filters on quality,
caps a family or refuses a cell for being numerous -- L1.60 holds: everything discovered reaches
the gauntlet and the gauntlet decides, with its own sealed constants and a trial count that
`policy/gate_spec.yaml` pins as a CONSTANT, so volume costs no other cell a thing.

THE THREE THINGS A ROW MUST HAVE to be judged, and they are the merge's and the judge's rules,
not this module's inventions:
  * a symbol the desk can actually replay and trade (`merge_hypotheses.tradeable_universe`);
  * a family, because a family-less row is unroutable;
  * a POINT-IN-TIME STAMP, through the desk's one door (`libs.data.pit.stamp_or_refuse`), or the
    gauntlet refuses it at the PIT ratchet. A registry candidate's `created_at` IS its
    available_time -- the moment the hypothesis became knowable to this desk -- so the stamp is
    read off the row rather than minted for it, and a row that cannot carry one is REFUSED and
    counted rather than fed unstamped.

WHAT IT DELIBERATELY DOES NOT CARRY. Rows already judged (`judged_at` set) and rows the desk has
certified are left out -- not to shrink the docket, which is a BANK and keeps them, but because
the feed's job is the UNJUDGED frontier and re-feeding a verdict the registry already holds buys
nothing. The banned-from-live families are dropped for the same reason `merge_hypotheses` drops
them: a cell that cannot reach the book cannot repay a gate-second.
"""
from __future__ import annotations

import contextlib
import json
import sqlite3
from collections.abc import Iterator, Mapping
from typing import Any

from libs.moat import registry as R

#: Where a candidate's chart lives on the docket row. The gauntlet reads `timeframe` off the row
#: and folds it into `params` itself when it is not H1, so two charts of one rule stay two cells.
DEFAULT_CHART = "H1"
#: The source label the merge and every downstream census will see. One name, so
#: `external_survivors.json`'s `by_source` accounting can say how much of the docket this is.
SOURCE = "moat_registry"


def _params(blob: Any) -> dict[str, Any]:
    if isinstance(blob, dict):
        return dict(blob)
    try:
        got = json.loads(blob or "{}")
    except (TypeError, ValueError):
        return {}
    return got if isinstance(got, dict) else {}


def _row(c: Mapping[str, Any]) -> dict[str, Any] | None:
    """One registry candidate as a docket row, or None when it names no executable cell."""
    sym = str(c.get("symbol") or "").strip()
    fam = str(c.get("family") or "").strip()
    if not sym or not fam:
        return None
    chart = str(c.get("chart") or "").strip().upper() or DEFAULT_CHART
    return {
        "symbol": sym,
        "family": fam,
        "params": _params(c.get("params_json")),
        "timeframe": chart,
        "source": SOURCE,
        "title": f"{sym} {fam} @{chart} (registry {c.get('id')})",
        "candidate_id": str(c.get("id") or ""),
        "origin": str(c.get("origin") or ""),
        "mechanism": str(c.get("mechanism") or "")[:400],
        "grid_cell": str(c.get("grid_cell") or ""),
        "score": c.get("score"),
        # THE CANDIDATE'S OWN BIRTH IS ITS available_time. `libs.data.pit.stamp` preserves a field
        # the producer already set, so this is the registry's recorded time and not `now()`.
        "available_time": str(c.get("created_at") or ""),
        "payload_hash": str(c.get("content_hash") or ""),
    }


def candidate_rows(conn: sqlite3.Connection, *, tradeable: Mapping[str, str] | None = None,
                   banned: frozenset[str] | None = None,
                   batch: int = 20000) -> Iterator[dict[str, Any]]:
    """Every UNJUDGED registry candidate that names an executable cell, as a docket row.

    Streamed rather than listed: the registry holds hundreds of thousands of these and the caller
    is already holding the whole docket bank in memory.
    """
    ban = banned or frozenset()
    cur = conn.execute(
        "SELECT id, symbol, family, params_json, chart, origin, mechanism, grid_cell, score,"
        " created_at, content_hash FROM research_candidates "
        "WHERE symbol IS NOT NULL AND symbol != '' AND family IS NOT NULL AND family != '' "
        "AND judged_at IS NULL AND COALESCE(status,'') != 'survived' ORDER BY score DESC, seq")
    while True:
        chunk = cur.fetchmany(batch)
        if not chunk:
            return
        for raw in chunk:
            row = _row(dict(raw))
            if row is None:
                continue
            if row["family"].lower() in ban:
                continue
            if tradeable is not None and row["symbol"].upper() not in tradeable:
                continue
            yield row


def feed(conn: sqlite3.Connection | None = None, *,
         tradeable: Mapping[str, str] | None = None,
         banned: frozenset[str] | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """(stamped docket rows, the census). Never raises: a feed that fails is a measured zero.

    The census is the artifact. `refused_unstamped` is a real number and never a silence -- the
    desk has already paid once for a stamper failure that produced unstamped rows looking exactly
    like stamped ones (2026-09-05, 0 of 4,768 rows carried `available_time` and nothing noticed).
    """
    census: dict[str, Any] = {"source": SOURCE, "status": "UNMEASURED", "candidates": 0,
                              "fed": 0, "refused_unstamped": 0, "refusals": []}
    own = conn is None
    try:
        c = conn or R.connect()
    except Exception as exc:
        census["why"] = f"registry unavailable: {type(exc).__name__}: {exc}"
        return [], census
    try:
        raw = list(candidate_rows(c, tradeable=tradeable, banned=banned))
        census["candidates"] = len(raw)
        from libs.data.pit import stamp_or_refuse
        rows, refused = stamp_or_refuse(raw, SOURCE)
        census["fed"] = len(rows)
        census["refused_unstamped"] = len(refused)
        census["refusals"] = refused[:20]
        census["status"] = "MEASURED"
        return rows, census
    except Exception as exc:
        census["why"] = f"{type(exc).__name__}: {exc}"
        return [], census
    finally:
        if own:
            with contextlib.suppress(Exception):
                c.close()
