"""THE BIRTH RECORD OF EVERY CERTIFICATE -- which producer earned it, joined by EXACT identity
only, and UNMEASURED by name where no exact route reaches it.

    python desks/mt5/research/certificate_provenance.py --once --budget-s 600

THE DEFECT THIS CLOSES (measured 2026-09-24 on the trading box). The desk held 174 ten-gate
certificates and could not name the producer that earned a single one. Every row of
`data/UNIVERSAL_SURVIVORS.canon.json` carries `hunt`, `cell`, `sym`, `days`, the ten gate results
and `gated_at`, and NOTHING about who found it -- the sealed gauntlet writes that file and does
not know. So against ~1,982 producers and 102 seats the desk could not tell which deserved
compute, and the standing order to maximise conversion was unmeasurable.

AND THE NUMBER THAT WAS PUBLISHED WAS WORSE THAN THE GAP. `ATTRIBUTION_COVERAGE.json` reported
`certificates: coverage 1.0, attributed 52/52` with a `by_producer` histogram. Measured: ALL of
them came through the `symbol|family -> candidate` fallback, whose index is built with
`setdefault` over rowid order -- and between 105 and 437 candidates share each (symbol, family)
pair, spread over six or more distinct producers. Every one of those attributions was an
arbitrary pick wearing a measurement's clothes, and a wrong attribution is worse than none
because it misdirects compute. This module refuses that route by construction.

FOUR ROUTES, ALL EXACT, ALL THE DESK'S ONE IDENTITY. `research/frontier_identity.cell_id` is the
rule the sealed gauntlet itself uses to name a cell (`<sym>[@TF].<family>.p=<sha of params>`), so
every route below RECOMPUTES it from the store's own columns rather than matching names:

    registry_identity  research_candidates.symbol/family/params_json -> cell_id -> `producer`,
                       the stamp libs/research/attribution.attribute() wrote AT BIRTH
    docket             data/hypotheses/external_survivors.json, the one file the judge opens,
                       whose rows carry `producer` and `source` -> cell_id
    verdict_graph      gate_verdict_ledger.jsonl `cell` -> `graph_id` -> hypothesis_graph.jsonl
                       `id` -> `source`
    graph_identity     hypothesis_graph.jsonl symbol/family/params -> cell_id -> `source`

FOUR VERDICTS, AND THE DIFFERENCE IS THE WHOLE POINT (L1.28a):

    ATTRIBUTED   exactly one producer names this cell across every route that reached it
    FIRST_CLAIM  several producers name it and one is STRICTLY earliest by its own recorded
                 creation time -- a co-discovered cell, credited to the one that proposed it
                 first, with every claimant listed beside it
    AMBIGUOUS    several producers name it and none is strictly earliest -- recorded, never
                 broken by a tie-break the evidence does not support
    UNMEASURED   no exact route reaches it, with the reason; never a guess, never a producer
                 inferred from a family name

INCREMENTAL BY CONSTRUCTION. A certificate is immutable once minted (`gated_at`, `canon_sha256`),
so a record that reached a final verdict is never recomputed. Only cells with no record, or one
truncated by a budget, pay for the expensive passes -- which is why this can ride the hourly
census leg instead of needing a clock of its own.

Artifacts: `desks/mt5/data/certificate_provenance.json` (the birth record, one row per
certificate -- the authority the fence reads) and `desks/mt5/reports/PRODUCER_CONVERSION.json`
(the conversion table: donations, docket, judged, certificates, per producer).
Clock:      `hourly_cycle:attribution_census`, which calls `refresh()` with its remaining budget.
Fence:      `scripts/check_birth_obligations.py`, axis `certificate_birth` -- a certificate with
            no row in the record file is an arrival that fails, and UNMEASURED-with-a-reason
            satisfies the obligation exactly as it does on the attribution axis.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import attribution as A  # noqa: E402
from libs.research import source_provenance as SP  # noqa: E402

REGISTRY = ROOT / "data" / "alpha_registry.sqlite"
#: The canonical certificate store. `reports/UNIVERSAL_SURVIVORS.json` is its published twin; both
#: are read, never written -- the sealed gauntlet owns them.
CANON = DESK / "data" / "UNIVERSAL_SURVIVORS.canon.json"
SURVIVORS = DESK / "reports" / "UNIVERSAL_SURVIVORS.json"
DOCKET = DESK / "data" / "hypotheses" / "external_survivors.json"
VERDICTS = DESK / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"
GRAPH = DESK / "data" / "hypothesis_graph.jsonl"

RECORD = DESK / "data" / "certificate_provenance.json"
TABLE = DESK / "reports" / "PRODUCER_CONVERSION.json"

ATTRIBUTED = "ATTRIBUTED"
FIRST_CLAIM = "FIRST_CLAIM"
AMBIGUOUS = "AMBIGUOUS"
UNMEASURED = A.UNMEASURED

#: Every verdict a finished record may carry. A record whose verdict is here and whose `final` is
#: true is never recomputed: a certificate is immutable once minted.
VERDICT_ORDER = (ATTRIBUTED, FIRST_CLAIM, AMBIGUOUS, UNMEASURED)

#: The four exact routes. A pass on which one of them could not run leaves UNMEASURED non-final.
ALL_ROUTES = ("registry_identity", "docket", "verdict_graph", "graph_identity")

LAW = ("EVERY CERTIFICATE NAMES THE PRODUCER THAT EARNED IT, joined by the desk's one cell "
       "identity and never by a symbol/family fallback that several hundred candidates share. A "
       "certificate no exact route reaches is UNMEASURED with its reason -- a wrong attribution "
       "is worse than none, because it misdirects compute (L1.28a).")

RULE = ("producer = the organ named by an EXACT cell-identity join into the registry's birth "
        "stamp, the judge's own docket, the verdict ledger's graph edge, or the hypothesis "
        "graph; several claimants resolve to the strictly earliest by recorded creation time and "
        "are listed in full; a tie is AMBIGUOUS and no route is a name match")

#: Lines of `hypothesis_graph.jsonl` are parsed only when a cheap substring pre-filter says the
#: line could name a wanted cell. The graph holds ~4.2M rows and json.loads on every one of them
#: costs minutes; the pre-filter makes the pass proportional to what is actually being looked for.
_PREFILTER_MIN_TOKENS = 1


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _atomic(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _cell_id() -> Any:
    """The desk's ONE cell identity, imported and never re-implemented. None when unreachable,
    which makes every route UNMEASURED rather than silently matching on a second rule."""
    try:
        from frontier_identity import cell_id  # type: ignore[import-not-found]
    except ImportError:
        try:
            from research.frontier_identity import (  # type: ignore[no-redef,unused-ignore]
                cell_id,
            )
        except ImportError:                                              # pragma: no cover
            return None
    return cell_id


def certificates(doc: Any = None) -> dict[str, dict[str, Any]]:
    """`{certificate key: row}` from the canonical store, falling back to its published twin.

    Both files carry the same 174 keys today; the canon is read first because it is the store the
    promoter and the clocks resolve against.
    """
    if doc is None:
        doc = _json(CANON)
        if not isinstance(doc, dict) or not isinstance(doc.get("survivors"), dict):
            doc = _json(SURVIVORS)
    if not isinstance(doc, dict):
        return {}
    surv = doc.get("survivors")
    if not isinstance(surv, dict):
        return {}
    return {str(k): (v if isinstance(v, dict) else {}) for k, v in surv.items()}


def cell_of(key: str, row: dict[str, Any]) -> str:
    """The cell identity a certificate was minted under: its own `cell` field, else its key with
    the leading `<hunt>.` stripped. Never recomputed from `shadow_spec`, which carries a selector
    the gauntlet's own `cell_id` does not put in the name."""
    cell = str(row.get("cell") or "").strip()
    if cell:
        return cell
    hunt = str(row.get("hunt") or "").strip()
    k = str(key)
    return k[len(hunt) + 1:] if hunt and k.startswith(hunt + ".") else k


#: Suffixes that make a token a FILE the cell arrived in, never the organ that produced it. A
#: docket row whose `source` is `external_backtest_results.json` records a route and no producer;
#: crediting 7 certificates to a filename would tell the principal to give compute to a file.
_FILE_SUFFIXES = (".json", ".jsonl", ".csv", ".parquet", ".txt", ".yaml", ".yml", ".sqlite")


def _is_file_token(name: str) -> bool:
    return name.lower().endswith(_FILE_SUFFIXES)


def _claim(store: dict[str, dict[str, dict[str, Any]]], cell: str, producer: object,
           route: str, when: object, detail: dict[str, Any] | None = None) -> None:
    """Record that `producer` names `cell`, by `route`, first seen at `when`.

    A token that names a FILE is not a claim. It is where the cell was read from, and recording it
    as the producer would put a filename at the top of a table whose whole purpose is deciding
    which organs deserve compute.
    """
    name = A.normalise_producer(producer) or str(producer or "").strip()
    if not name or name == A.UNATTRIBUTABLE or _is_file_token(name):
        return
    slot = store.setdefault(cell, {})
    cur = slot.get(name)
    stamp = str(when or "")
    if cur is None:
        slot[name] = {"routes": [route], "first_seen": stamp, "detail": detail or {}}
        return
    if route not in cur["routes"]:
        cur["routes"].append(route)
    if stamp and (not cur.get("first_seen") or stamp < str(cur["first_seen"])):
        cur["first_seen"] = stamp


# ------------------------------------------------------------------------------- the four routes

def route_registry(conn: sqlite3.Connection, want: dict[str, str],
                   store: dict[str, dict[str, dict[str, Any]]]) -> dict[str, Any]:
    """The birth stamp itself: recompute each candidate's cell identity from its OWN columns.

    Narrowed to the (symbol, family) pairs the wanted cells use, so the pass is proportional to
    what is being looked for rather than to the 709,706-row table.
    """
    cid = _cell_id()
    if cid is None:
        return {"available": False, "why": f"{UNMEASURED}: frontier_identity.cell_id unreachable"}
    pairs = {(c.split(".")[0].split("@")[0].upper(), _family_of(c)) for c in want}
    pairs.discard(("", ""))
    if not pairs:
        return {"available": True, "rows": 0, "hits": 0}
    syms = sorted({p[0] for p in pairs if p[0]})
    fams = sorted({p[1] for p in pairs if p[1]})
    if not syms or not fams:
        return {"available": True, "rows": 0, "hits": 0}
    q = ("SELECT symbol, family, params_json, "  # noqa: S608 -- column names are module literals
         f"coalesce({A.PRODUCER_FIELD},''), coalesce({A.REGION_FIELD},''), id, created_at "
         f"FROM research_candidates WHERE upper(symbol) IN ({','.join('?' * len(syms))}) "
         f"AND family IN ({','.join('?' * len(fams))})")
    rows = hits = 0
    try:
        cur = conn.execute(q, (*syms, *fams))
    except sqlite3.Error as exc:
        return {"available": False, "why": f"{UNMEASURED}: registry unreadable ({exc})"}
    for sym, fam, pj, who, region, rid, created in cur:
        rows += 1
        try:
            params = json.loads(pj) if pj else {}
        except ValueError:
            params = {}
        if not isinstance(params, dict):
            params = {}
        try:
            key = cid({"sym": sym, "family": fam, "params": params})
        except (KeyError, TypeError, ValueError):
            continue
        if key in want:
            hits += 1
            _claim(store, key, who, "registry_identity", created,
                   {"candidate_id": str(rid), "region": str(region or "")})
    return {"available": True, "rows": rows, "hits": hits,
            "basis": "research_candidates.symbol/family/params_json -> frontier_identity.cell_id"}


def _family_of(cell: str) -> str:
    """The family token of a cell identity `<sym>[@TF].<family>.p=<sha>`. Consumers split on '.'
    and the chart rides on the SYMBOL, so the family is always the second field."""
    bits = str(cell).split(".")
    return bits[1] if len(bits) >= 2 else ""


def route_docket(want: dict[str, str], store: dict[str, dict[str, dict[str, Any]]],
                 deadline: float | None = None, path: Path | None = None, *,
                 lineage: dict[str, list[dict[str, Any]]] | None = None,
                 aliases: dict[str, str] | None = None,
                 claim_cells: set[str] | None = None) -> dict[str, Any]:
    """The judge's own input: every row `scripts/external_gauntlet.py` opens carries `producer`
    and `source` beside the symbol, family and params its cell identity is computed from.

    `lineage`, when given, collects every docket row that recomputes to a wanted cell -- or to
    its SPEC identity in `aliases` (the cell id recomputed from the certificate's own
    `shadow_spec`, `{spec id: cell}`) -- as the next link of the SOURCE lineage. Aliases feed the
    lineage only, never a producer claim: the attribution stays on the exact cell. `claim_cells`
    limits which cells take producer claims (a final record is never re-attributed)."""
    p = path or DOCKET
    cid = _cell_id()
    if cid is None:
        return {"available": False, "why": f"{UNMEASURED}: frontier_identity.cell_id unreachable"}
    if not p.exists():
        return {"available": False, "why": f"{UNMEASURED}: no docket at {p.as_posix()}"}
    size = p.stat().st_size
    free = _free_bytes()
    # THE DOCKET IS 448 MB OF PRETTY-PRINTED JSON and parsing it costs several times that in
    # objects. Refusing with the measured reason beats being killed mid-pass on the 8 GB box,
    # and the cells stay pending rather than being recorded as unreachable (L1.28a).
    if free is not None and size * 8 > free:
        return {"available": False,
                "why": f"{UNMEASURED}: docket is {size/1e6:.0f} MB and only {free/1e6:.0f} MB of "
                       f"physical memory is free; parsing it needs several times its size"}
    try:
        rows = json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, MemoryError) as exc:
        return {"available": False, "why": f"{UNMEASURED}: docket unreadable ({exc})"}
    if not isinstance(rows, list):
        return {"available": False, "why": f"{UNMEASURED}: docket is not a list of rows"}
    n = hits = 0
    for r in rows:
        if not isinstance(r, dict):
            continue
        n += 1
        if deadline is not None and n % 20000 == 0 and time.monotonic() > deadline:
            return {"available": True, "rows": n, "hits": hits, "truncated": True,
                    "why": "budget exhausted inside the docket pass"}
        try:
            key = cid({"sym": r.get("symbol"), "family": r.get("family"),
                       "params": r.get("params") or {}, "timeframe": r.get("timeframe")})
        except (KeyError, TypeError, ValueError):
            continue
        via = "cell_id" if key in want else ("spec_frontier_id" if aliases and key in aliases
                                             else "")
        if not via:
            continue
        cell = key if via == "cell_id" else str((aliases or {})[key])
        if lineage is not None:
            lineage.setdefault(cell, []).append(_docket_link(r, n - 1, via, p))
        if via == "cell_id" and (claim_cells is None or key in claim_cells):
            hits += 1
            _claim(store, key, r.get("producer") or r.get("source"), "docket",
                   r.get("first_seen") or r.get("available_time"),
                   {"source": str(r.get("source") or ""),
                    "candidate_id": str(r.get("candidate_id") or ""),
                    "url": str(r.get("url") or "")})
    return {"available": True, "rows": n, "hits": hits, "truncated": False,
            "basis": "data/hypotheses/external_survivors.json -> frontier_identity.cell_id"}


# ------------------------------------------------------------------------ the SOURCE lineage
#
# THE PRODUCER IS HALF THE BIRTH RECORD. The verdicts above say WHICH ORGAN earned a certificate;
# the lineage below says WHAT IT READ: certificate -> docket row (by the cell identity, or by the
# identity recomputed from the certificate's own `shadow_spec`) -> the donation that put the row
# there (producer, source, candidate / genome id) -> the source row (URL or source id, retrieval
# time, content hash, in `libs.research.source_provenance`'s vocabulary). Where a link is absent
# the lineage ENDS THERE, as UNMEASURED with the link it stopped at -- never a URL borrowed from a
# neighbouring cell (L1.28a).

LINEAGE_MEASURED = "MEASURED"


def spec_cell(row: dict[str, Any]) -> str:
    """The cell identity recomputed from the certificate's own `shadow_spec`, '' when it has none.
    A LOOKUP KEY for the lineage, never the certificate's name (see `cell_of`)."""
    spec = row.get("shadow_spec") if isinstance(row, dict) else None
    cid = _cell_id()
    if not isinstance(spec, dict) or cid is None:
        return ""
    try:
        return str(cid({"sym": spec.get("symbol") or row.get("sym"),
                        "family": spec.get("family"), "params": spec.get("params") or {},
                        "timeframe": spec.get("timeframe")}))
    except (KeyError, TypeError, ValueError):
        return ""


def _docket_link(r: dict[str, Any], idx: int, via: str, path: Path) -> dict[str, Any]:
    """One docket row as a lineage link: its donation coordinate and its source provenance."""
    try:
        rel = path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        rel = path.as_posix()
    # NO `artifact` coordinate: the docket's own file#row would read as a source id and turn
    # every lineage MEASURED while naming nothing upstream of the judge's input.
    prov = SP.extract(r)
    if not prov.get("retrieved_at") and r.get("first_seen"):
        prov["retrieved_at"], prov["retrieved_at_basis"] = str(r["first_seen"]), "docket:first_seen"
    contrib = r.get("contributing_sources")
    return {"joined_by": via, "docket_row": idx, "docket": f"{rel}#{idx}",
            "producer": str(r.get("producer") or ""), "source": str(r.get("source") or ""),
            "candidate_id": str(r.get("candidate_id") or ""),
            "genome_id": str(r.get("genome_id") or ""),
            "first_seen": r.get("first_seen") or r.get("available_time"),
            "contributing_sources": list(contrib)[:8] if isinstance(contrib, list) else [],
            "n_independent_sources": r.get("n_independent_sources"),
            **{k: prov.get(k) for k in SP.FIELDS if k in prov},
            "retrieved_at_basis": prov.get("retrieved_at_basis"),
            "content_hash_basis": prov.get("content_hash_basis")}


def source_lineage(key: str, row: dict[str, Any], cell: str,
                   links: list[dict[str, Any]] | None, docket_route: dict[str, Any] | None,
                   record: dict[str, Any] | None = None) -> dict[str, Any]:
    """Walk certificate -> docket row -> donation -> source row, stopping honestly.

    Returns `{"status": MEASURED | UNMEASURED, "ends_at": <link>, "why", "steps", ...}`. A lineage
    whose docket pass never ran is UNMEASURED and NOT final, so the next pass retries it."""
    steps: list[dict[str, Any]] = [{"link": "certificate", "key": key, "cell": cell,
                                    "gated_at": row.get("gated_at"),
                                    "spec_cell": spec_cell(row) or None}]
    out: dict[str, Any] = {"status": UNMEASURED, "at": _now(), "steps": steps, "final": True}
    if not (docket_route or {}).get("available") or (docket_route or {}).get("truncated"):
        out.update({"ends_at": "certificate", "final": False,
                    "why": "the docket pass did not complete this run ("
                           + str((docket_route or {}).get("why") or "not run") + ")"})
        return out
    if not links:
        out.update({"ends_at": "certificate",
                    "why": "no docket row recomputes to this cell id or to the id of its own "
                           "shadow_spec; the certificate outlived the docket row it was judged "
                           "from"})
        return out
    # The EARLIEST docket row is the one the judge saw first; the rest are counted, not merged.
    ordered = sorted(links, key=lambda d: (str(d.get("first_seen") or "~"), d["docket_row"]))
    best = ordered[0]
    steps.append({"link": "docket", "row": best["docket_row"], "joined_by": best["joined_by"],
                  "first_seen": best.get("first_seen"), "n_rows": len(links)})
    if _is_file_token(str(best.get("producer") or "")):
        # A FILE is the route the row arrived by, never the organ that donated it (see _claim).
        best = {**best, "route_file": best.get("producer"), "producer": ""}
    donor = best.get("producer") or best.get("source")
    donation_id = best.get("candidate_id") or best.get("genome_id")
    claim = ((record or {}).get("claimants") or {}).get(str((record or {}).get("producer") or ""))
    if not donation_id and isinstance(claim, dict):
        donation_id = claim.get("candidate_id") or claim.get("graph_id") or ""
    if not donor and not donation_id:
        out.update({"ends_at": "docket",
                    "why": "the docket row names no producer, source, candidate or genome id, "
                           "so no donation can be walked to"})
        return out
    steps.append({"link": "donation", "producer": best.get("producer") or None,
                  "route_file": best.get("route_file") or None,
                  "source": best.get("source") or None, "id": donation_id or None,
                  "contributing_sources": best.get("contributing_sources") or []})
    url = str(best.get("source_url") or "")
    sid = str(best.get("source_id") or "")
    if not url and not sid:
        out.update({"ends_at": "donation",
                    "why": f"the docket row for this donation ({donor or donation_id}) names no "
                           "source URL or source id; an internal generator reads no page, and "
                           "an external row minted before source stamping lost it -- which of "
                           "the two is not recorded, so the lineage ends here"})
        return out
    steps.append({"link": "source", "source_url": url or None, "source_id": sid or None})
    out.update({"status": LINEAGE_MEASURED, "ends_at": "source",
                "why": f"walked to the source by {best['joined_by']}",
                "source_url": url or None, "source_id": sid or None,
                "ground": best.get("ground") or None,
                "retrieved_at": best.get("retrieved_at"),
                "retrieved_at_basis": best.get("retrieved_at_basis"),
                "content_hash": best.get("content_hash"),
                "content_hash_basis": best.get("content_hash_basis")})
    return out


def route_graph(want: dict[str, str], store: dict[str, dict[str, dict[str, Any]]],
                deadline: float | None = None, verdicts: Path | None = None,
                graph: Path | None = None) -> dict[str, Any]:
    """Two routes in ONE pass over the 4.2M-row hypothesis graph, because it is the expensive file.

    `verdict_graph` follows the gate ledger's own `graph_id` edge to the node that was judged;
    `graph_identity` recomputes the cell identity from the node's own symbol, family and params.
    They are independent of each other and of the registry, which is why agreement between them
    is evidence and not a coincidence.
    """
    vp = verdicts or VERDICTS
    gp = graph or GRAPH
    cid = _cell_id()
    out: dict[str, Any] = {"available": True, "verdict_rows": 0, "graph_rows": 0,
                           "graph_parsed": 0, "wanted_graph_ids": 0, "hits": 0}
    gid_want: dict[str, set[str]] = {}
    if vp.exists():
        try:
            with vp.open(encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        o = json.loads(line)
                    except ValueError:
                        continue
                    if not isinstance(o, dict):
                        continue
                    out["verdict_rows"] += 1
                    cell = str(o.get("cell") or "")
                    gid = str(o.get("graph_id") or "")
                    if cell in want and gid:
                        gid_want.setdefault(gid, set()).add(cell)
        except OSError as exc:
            out["verdict_why"] = f"{UNMEASURED}: verdict ledger unreadable ({exc})"
    else:
        out["verdict_why"] = f"{UNMEASURED}: no verdict ledger at {vp.as_posix()}"
    out["wanted_graph_ids"] = len(gid_want)

    if not gp.exists():
        out["graph_why"] = f"{UNMEASURED}: no hypothesis graph at {gp.as_posix()}"
        return out
    # THE PRE-FILTER. A line is parsed only when it could name something wanted: one of the
    # graph ids the verdicts pointed at, or one of the symbols the wanted cells use. Without it
    # this pass json.loads 4.2M rows to find at most a few hundred.
    tokens = set(gid_want)
    tokens |= {c.split(".")[0].split("@")[0] for c in want}
    tokens = {t for t in tokens if len(t) >= _PREFILTER_MIN_TOKENS}
    try:
        with gp.open(encoding="utf-8", errors="replace") as f:
            for line in f:
                out["graph_rows"] += 1
                if deadline is not None and out["graph_rows"] % 100000 == 0 \
                        and time.monotonic() > deadline:
                    out["truncated"] = True
                    out["why"] = "budget exhausted inside the hypothesis-graph pass"
                    return out
                if not any(t in line for t in tokens):
                    continue
                try:
                    o = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(o, dict):
                    continue
                out["graph_parsed"] += 1
                src = o.get("source")
                when = o.get("at") or o.get("created_at") or o.get("first_seen")
                nid = str(o.get("id") or "")
                for cell in gid_want.get(nid, ()):  # route: verdict_graph
                    out["hits"] += 1
                    _claim(store, cell, src, "verdict_graph", when, {"graph_id": nid})
                if cid is not None and o.get("symbol") and o.get("family"):
                    try:
                        key = cid({"sym": o.get("symbol"), "family": o.get("family"),
                                   "params": o.get("params") or {}})
                    except (KeyError, TypeError, ValueError):
                        continue
                    if key in want:
                        out["hits"] += 1
                        _claim(store, key, src, "graph_identity", when, {"graph_id": nid})
    except OSError as exc:
        out["graph_why"] = f"{UNMEASURED}: hypothesis graph unreadable ({exc})"
    out["truncated"] = False
    return out


def _free_bytes() -> int | None:
    """Free physical memory on THIS machine, measured. The two boxes differ by twelve times and
    every hard-coded figure this desk has written down has been wrong within a fortnight."""
    try:
        import psutil  # type: ignore[import-untyped,unused-ignore]
        return int(psutil.virtual_memory().available)
    except Exception:                                                    # pragma: no cover
        return None


# ------------------------------------------------------------------------------- the birth record

def judge(cell: str, claims: dict[str, dict[str, Any]], routes_ran: list[str]) -> dict[str, Any]:
    """One certificate's verdict from every claim the exact routes recorded.

    A single claimant is ATTRIBUTED. Several resolve to the strictly earliest by recorded
    creation time (FIRST_CLAIM) with the whole claimant list beside it, or AMBIGUOUS when the
    earliest is not unique -- the tie is recorded, never broken by a rule the evidence does not
    carry. No claimant at all is UNMEASURED with the routes that looked.
    """
    base: dict[str, Any] = {"cell": cell, "routes_ran": list(routes_ran), "at": _now()}
    if not claims:
        base.update({"verdict": UNMEASURED, "producer": None, "final": True,
                     "why": f"no exact identity route reaches this cell "
                            f"({', '.join(routes_ran) or 'no route ran'})"})
        return base
    names = sorted(claims)
    base["claimants"] = {n: {"routes": sorted(claims[n]["routes"]),
                             "first_seen": claims[n].get("first_seen") or None,
                             **{k: v for k, v in (claims[n].get("detail") or {}).items() if v}}
                         for n in names}
    base["n_claimants"] = len(names)
    if len(names) == 1:
        who = names[0]
        base.update({"verdict": ATTRIBUTED, "producer": who, "final": True,
                     "routes": sorted(claims[who]["routes"]),
                     "region": _region_for(who, claims[who]),
                     "why": f"exactly one producer names this cell, by "
                            f"{', '.join(sorted(claims[who]['routes']))}"})
        return base
    stamped = [(str(claims[n].get("first_seen") or ""), n) for n in names]
    dated = sorted((s, n) for s, n in stamped if s)
    if dated and (len(dated) == 1 or dated[0][0] < dated[1][0]):
        who = dated[0][1]
        base.update({"verdict": FIRST_CLAIM, "producer": who, "final": True,
                     "routes": sorted(claims[who]["routes"]),
                     "region": _region_for(who, claims[who]),
                     "first_claim_at": dated[0][0],
                     "why": f"{len(names)} producers name this cell; {who} proposed it first at "
                            f"{dated[0][0]} -- co-discovery, credited to the first claim"})
        return base
    base.update({"verdict": AMBIGUOUS, "producer": None, "final": True,
                 "why": f"{len(names)} producers name this cell and none is strictly earliest by "
                        f"recorded creation time; the tie is recorded, not broken"})
    return base


def _region_for(who: str, claim: dict[str, Any]) -> str:
    """The producer's region, through the ONE helper. A stamped region from the registry route
    wins because it was written at birth; otherwise the helper derives it from the name."""
    stamped = str((claim.get("detail") or {}).get("region") or "")
    if stamped:
        return stamped
    if A.is_non_regional(who):
        return A.NOT_REGIONAL
    return A.region_of(who) or A.UNATTRIBUTABLE


def refresh(budget_s: float = 240.0, *, retry_unmeasured: bool = False,
            rebuild: bool = False, conn: sqlite3.Connection | None = None) -> dict[str, Any]:
    """Bring the birth record up to date, then publish the conversion table.

    Only certificates with no record, or one a budget truncated, pay for the expensive passes --
    a certificate is immutable once minted, so a final verdict is never recomputed.
    """
    t0 = time.monotonic()
    deadline = t0 + max(5.0, float(budget_s))
    doc: dict[str, Any] = {"at": _now(), "law": LAW, "rule": RULE,
                           "identity": "desks/mt5/research/frontier_identity.cell_id",
                           "canon": CANON.as_posix(), "record": RECORD.as_posix(),
                           "table": TABLE.as_posix()}
    certs = certificates()
    doc["n_certificates"] = len(certs)
    if not certs:
        doc.update({"available": False,
                    "why": f"{UNMEASURED}: no certificate store readable at "
                           f"{CANON.as_posix()} or {SURVIVORS.as_posix()}"})
        return doc

    prior_doc = None if rebuild else _json(RECORD)
    prior: dict[str, Any] = {}
    if isinstance(prior_doc, dict) and isinstance(prior_doc.get("records"), dict):
        prior = dict(prior_doc["records"])

    cell_by_key = {k: cell_of(k, r) for k, r in certs.items()}
    want: dict[str, str] = {}
    for key, cell in cell_by_key.items():
        rec = prior.get(cell)
        if (isinstance(rec, dict) and rec.get("final")
                and rec.get("verdict") in VERDICT_ORDER
                and not (retry_unmeasured and rec.get("verdict") == UNMEASURED)):
            continue
        want[cell] = key
    doc["pending"] = len(want)
    doc["warm"] = len(set(cell_by_key.values())) - len(want)
    # THE SOURCE LINEAGE IS BACKFILLED ON FINAL RECORDS TOO: a record written before the lineage
    # existed carries a producer and nothing about what it read, and a certificate is immutable,
    # so walking its lineage once is never a re-attribution. Only the docket pass is paid for it.
    lineage_want: dict[str, str] = {}
    for key, cell in cell_by_key.items():
        rec = prior.get(cell)
        lin = rec.get("source_lineage") if isinstance(rec, dict) else None
        if cell in want or not (isinstance(lin, dict) and lin.get("final")):
            lineage_want[cell] = key
    aliases: dict[str, str] = {}
    for cell, key in lineage_want.items():
        sc = spec_cell(certs[key])
        if sc and sc != cell:
            aliases.setdefault(sc, cell)
    doc["lineage_pending"] = len(lineage_want)

    store: dict[str, dict[str, dict[str, Any]]] = {}
    routes: dict[str, Any] = {}
    ran: list[str] = []
    links: dict[str, list[dict[str, Any]]] = {}
    if lineage_want and not want:
        routes["docket"] = route_docket({**lineage_want}, store, deadline=deadline,
                                        lineage=links, aliases=aliases, claim_cells=set())
    if want:
        own = conn
        c = own
        if c is None:
            try:
                c = sqlite3.connect(f"file:{REGISTRY}?mode=ro", uri=True)
            except sqlite3.Error as exc:
                routes["registry_identity"] = {"available": False,
                                               "why": f"{UNMEASURED}: registry unopenable ({exc})"}
                c = None
        if c is not None:
            routes["registry_identity"] = route_registry(c, want, store)
            if routes["registry_identity"].get("available"):
                ran.append("registry_identity")
            if own is None:
                c.close()
        routes["docket"] = route_docket({**lineage_want, **want}, store, deadline=deadline,
                                        lineage=links, aliases=aliases, claim_cells=set(want))
        if routes["docket"].get("available"):
            ran.append("docket")
        g = route_graph(want, store, deadline=deadline)
        routes["graph"] = g
        if g.get("available") and not g.get("truncated"):
            ran.extend(("verdict_graph", "graph_identity"))
    doc["routes"] = routes

    records: dict[str, Any] = {k: v for k, v in prior.items() if isinstance(v, dict)}
    truncated = any(bool(r.get("truncated")) for r in routes.values() if isinstance(r, dict))
    missing = [r for r in ALL_ROUTES if r not in ran]
    for cell in want:
        rec = judge(cell, store.get(cell) or {}, ran)
        if truncated and rec["verdict"] == UNMEASURED:
            rec["final"] = False
            rec["why"] = ("a route was truncated by the pass budget before this cell was "
                          "resolved; it stays pending and is retried next pass")
        elif missing:
            # A route that could not RUN is not a route that looked and found nothing: the
            # verdict stands with its reason, and the cell is retried when the store is readable
            # -- a named producer too, since the missing route may hold an earlier claimant.
            rec["final"] = False
            rec["why"] += (f"; not final -- {', '.join(missing)} could not run on this host, so "
                           "the cell is retried when they can")
        records[cell] = rec
    for cell, key in lineage_want.items():
        rec = records.get(cell)
        if isinstance(rec, dict):
            rec["source_lineage"] = source_lineage(key, certs[key], cell, links.get(cell),
                                                   routes.get("docket"), rec)
    # Certificates that have gone (a canon revocation) keep their record but are marked, so the
    # conversion table's denominator is today's store and the history is not silently rewritten.
    live = set(cell_by_key.values())
    for cell, rec in records.items():
        if isinstance(rec, dict):
            rec["in_canon"] = cell in live
    doc["records"] = records
    doc["keys"] = {k: cell_by_key[k] for k in sorted(cell_by_key)}
    doc["coverage"] = summarise(records, live)
    doc["elapsed_s"] = round(time.monotonic() - t0, 3)
    return doc


def summarise(records: dict[str, Any], live: set[str]) -> dict[str, Any]:
    """Coverage over the certificates the canon holds TODAY, by verdict and by producer."""
    by_verdict: dict[str, int] = {}
    by_producer: dict[str, int] = {}
    named = 0
    for cell in sorted(live):
        rec = records.get(cell)
        v = str((rec or {}).get("verdict") or "NO_RECORD")
        by_verdict[v] = by_verdict.get(v, 0) + 1
        who = (rec or {}).get("producer")
        if who:
            named += 1
            by_producer[str(who)] = by_producer.get(str(who), 0) + 1
    n = len(live)
    recorded = sum(v for k, v in by_verdict.items() if k != "NO_RECORD")
    lineage: dict[str, int] = {}
    ends: dict[str, int] = {}
    for cell in sorted(live):
        lin = (records.get(cell) or {}).get("source_lineage")
        st = str(lin.get("status")) if isinstance(lin, dict) else "NO_LINEAGE"
        lineage[st] = lineage.get(st, 0) + 1
        if isinstance(lin, dict):
            ends[str(lin.get("ends_at"))] = ends.get(str(lin.get("ends_at")), 0) + 1
    walked = n - lineage.get("NO_LINEAGE", 0)
    return {"n": n, "named": named, "unnamed": n - named,
            "coverage": round(named / n, 4) if n else UNMEASURED,
            # THE FENCED NUMBER: every certificate the store holds TODAY has a row. A row reading
            # UNMEASURED with its reason counts; a certificate with no row does not.
            "current_certificates": n, "recorded": recorded,
            "record_coverage": round(recorded / n, 4) if n else UNMEASURED,
            "source_lineage": {"walked": walked, "by_status": lineage, "ends_at": ends,
                               "measured": lineage.get(LINEAGE_MEASURED, 0),
                               "share_measured": (round(lineage.get(LINEAGE_MEASURED, 0) / n, 4)
                                                  if n else UNMEASURED)},
            "missing_record": by_verdict.get("NO_RECORD", 0),
            "by_verdict": dict(sorted(by_verdict.items(), key=lambda kv: -kv[1])),
            "by_producer": dict(sorted(by_producer.items(), key=lambda kv: -kv[1]))}


# --------------------------------------------------------------------------- the conversion table

def judged_by_identity(conn: sqlite3.Connection | None,
                       deadline: float | None = None) -> dict[str, Any]:
    """CELLS JUDGED, PER PRODUCER, by the same exact identity the certificates use.

    The gate verdict ledger names every cell the gauntlet judged. This builds
    `cell identity -> producers` from the registry's own columns in ONE pass and counts the
    distinct judged cells each producer owns. A cell several producers claim counts for each of
    them, which is the honest reading of a co-discovery: both did the work that got it judged.

    It is the one expensive stage that is not incremental, so it is deadline-bounded and reports
    UNMEASURED rather than a partial count that a reader would take for a total.
    """
    out: dict[str, Any] = {"available": False,
                           "basis": "gate_verdict_ledger.jsonl cells x research_candidates "
                                    "identity (frontier_identity.cell_id)"}
    cid = _cell_id()
    if conn is None or cid is None:
        out["why"] = f"{UNMEASURED}: no registry connection or no cell identity"
        return out
    if not VERDICTS.exists():
        out["why"] = f"{UNMEASURED}: no verdict ledger at {VERDICTS.as_posix()}"
        return out
    judged: set[str] = set()
    try:
        with VERDICTS.open(encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    o = json.loads(line)
                except ValueError:
                    continue
                if isinstance(o, dict) and o.get("cell"):
                    judged.add(str(o["cell"]))
    except OSError as exc:
        out["why"] = f"{UNMEASURED}: verdict ledger unreadable ({exc})"
        return out
    out["judged_cells"] = len(judged)
    if not judged:
        out.update({"available": True, "by_producer": {}, "matched_cells": 0})
        return out
    by_producer: dict[str, int] = {}
    matched = 0
    seen: set[tuple[str, str]] = set()
    try:
        cur = conn.execute(
            f"SELECT symbol, family, params_json, coalesce({A.PRODUCER_FIELD},'') "  # noqa: S608
            "FROM research_candidates WHERE symbol IS NOT NULL AND symbol != '' "
            "AND family IS NOT NULL AND family != ''")
        n = 0
        for sym, fam, pj, who in cur:
            n += 1
            if deadline is not None and n % 50000 == 0 and time.monotonic() > deadline:
                out["why"] = (f"{UNMEASURED}: the pass budget ran out after {n} candidates -- a "
                              f"partial count would read as a total")
                return out
            if not who:
                continue
            try:
                params = json.loads(pj) if pj else {}
            except ValueError:
                params = {}
            if not isinstance(params, dict):
                params = {}
            try:
                key = cid({"sym": sym, "family": fam, "params": params})
            except (KeyError, TypeError, ValueError):
                continue
            if key not in judged:
                continue
            name = A.normalise_producer(who) or str(who)
            if (name, key) in seen:
                continue
            seen.add((name, key))
            by_producer[name] = by_producer.get(name, 0) + 1
            matched += 1
        out["candidates_scanned"] = n
    except sqlite3.Error as exc:
        out["why"] = f"{UNMEASURED}: registry unreadable ({exc})"
        return out
    out.update({"available": True, "by_producer": by_producer,
                "matched_cells": len({k for _, k in seen}),
                "producer_cell_pairs": matched})
    return out


def conversion(conn: sqlite3.Connection | None, records: dict[str, Any],
               live: set[str], deadline: float | None = None) -> dict[str, Any]:
    """PER PRODUCER: donations made, cells that reached the docket, cells judged, certificates.

    The four stages come from the stores that own them and from nowhere else -- donations and the
    docket door and the judged stamp from the registry's own columns (the same definitions
    `productivity_census` already publishes), certificates from the birth record above. A producer
    that donated nothing in the window shows zeros, which is the measurement and not an absence.
    """
    out: dict[str, Any] = {"at": _now(), "law": LAW,
                           "stages": {
                               "donations": "registry discoveries + research_candidates, GROUP BY "
                                            "the producer stamped at birth",
                               "docket": "research_candidates with a donated_cell or a status past "
                                         "the judge's door (donated/claimed/judged/retired)",
                               "judged": "the gate verdict ledger's own cells, joined to the "
                                         "producer by EXACT cell identity -- the same rule the "
                                         "certificates use, so the two columns cannot contradict",
                               "judged_stamped": "research_candidates.judged_at, kept beside it "
                                                 "and NOT used: the pre-2026-09-23 verdict pour "
                                                 "joined on a cell name that matched nothing and "
                                                 "fell through to a symbol|family pick, so this "
                                                 "column reads 1,246 for `external` and 0 for "
                                                 "every producer that actually holds a "
                                                 "certificate. It heals as new verdicts pour "
                                                 "through libs/moat/registry.verdict_candidate",
                               "certificates": "desks/mt5/data/certificate_provenance.json, by "
                                               "EXACT cell identity only"}}
    rows: dict[str, dict[str, Any]] = {}

    def slot(who: str) -> dict[str, Any]:
        return rows.setdefault(who, {"producer": who, "region": None, "discoveries": 0,
                                     "candidates": 0, "docket": 0, "judged": UNMEASURED,
                                     "judged_stamped": 0,
                                     "certificates_sole": 0, "certificates_first_claim": 0,
                                     "certificates_shared": 0, "certificates": 0})

    if conn is None:
        out["registry"] = {"available": False, "why": f"{UNMEASURED}: registry unopenable"}
    else:
        try:
            for table, field in (("discoveries", "discoveries"),
                                 ("research_candidates", "candidates")):
                q = (f"SELECT coalesce(nullif({A.PRODUCER_FIELD},''),''), "  # noqa: S608
                     f"coalesce(nullif({A.REGION_FIELD},''),''), count(*) "
                     f"FROM {table} GROUP BY 1,2")
                for who, region, n in conn.execute(q):
                    name = str(who or "") or A.UNATTRIBUTABLE
                    s = slot(name)
                    s[field] += int(n or 0)
                    if s["region"] is None and region:
                        s["region"] = str(region)
            door = (f"SELECT coalesce(nullif({A.PRODUCER_FIELD},''),''), "  # noqa: S608
                    "count(*) FROM research_candidates "
                    "WHERE coalesce(donated_cell,'') != '' OR lower(coalesce(status,'')) IN "
                    "('donated','claimed','judged','retired','survived') GROUP BY 1")
            for who, n in conn.execute(door):
                slot(str(who or "") or A.UNATTRIBUTABLE)["docket"] += int(n or 0)
            jq = (f"SELECT coalesce(nullif({A.PRODUCER_FIELD},''),''), "  # noqa: S608
                  "count(*) FROM research_candidates "
                  "WHERE judged_at IS NOT NULL AND judged_at != '' GROUP BY 1")
            for who, n in conn.execute(jq):
                slot(str(who or "") or A.UNATTRIBUTABLE)["judged_stamped"] += int(n or 0)
            out["registry"] = {"available": True, "path": REGISTRY.as_posix()}
        except sqlite3.Error as exc:
            out["registry"] = {"available": False, "why": f"{UNMEASURED}: {exc}"}

    # THE JUDGED COLUMN, MEASURED THE SAME WAY THE CERTIFICATES ARE. Reading `judged_at` gave
    # `external` 1,246 judged cells and gave every producer that actually holds a certificate
    # ZERO -- a table that says a producer earned 68 certificates having never been judged is
    # telling the reader something false in the same row as something true. The verdict ledger is
    # the authority on what was judged; joining its cells by exact identity makes the two columns
    # answer to one rule. Unreachable is UNMEASURED per producer, never a zero (L1.28a).
    jd = judged_by_identity(conn, deadline=deadline)
    out["judged_census"] = {k: v for k, v in jd.items() if k != "by_producer"}
    if jd.get("available"):
        for who, n in (jd.get("by_producer") or {}).items():
            slot(str(who))["judged"] = int(n)
        for s in rows.values():
            if s["judged"] == UNMEASURED:
                s["judged"] = 0

    unnamed: dict[str, int] = {}
    for cell in sorted(live):
        rec = records.get(cell) or {}
        who = rec.get("producer")
        v = str(rec.get("verdict") or "NO_RECORD")
        if not who:
            unnamed[v] = unnamed.get(v, 0) + 1
            continue
        s = slot(str(who))
        s["certificates"] += 1
        if v == ATTRIBUTED:
            s["certificates_sole"] += 1
        elif v == FIRST_CLAIM:
            s["certificates_first_claim"] += 1
        if s["region"] is None:
            s["region"] = rec.get("region")
        for other in (rec.get("claimants") or {}):
            if str(other) != str(who):
                slot(str(other))["certificates_shared"] += 1

    for s in rows.values():
        d = s["candidates"] or 0
        s["docket_rate"] = round(s["docket"] / d, 4) if d else UNMEASURED
        s["judged_rate"] = round(s["judged"] / d, 4) if d else UNMEASURED
        j = s["judged"] if isinstance(s["judged"], int) else 0
        s["certificates_per_judged"] = round(s["certificates"] / j, 6) if j else UNMEASURED
        s["certificates_per_candidate"] = round(s["certificates"] / d, 8) if d else UNMEASURED
        if s["region"] is None:
            s["region"] = (A.NOT_REGIONAL if A.is_non_regional(s["producer"])
                           else A.region_of(s["producer"]) or A.UNATTRIBUTABLE)

    ordered = sorted(rows.values(),
                     key=lambda r: (-int(r["certificates"]),
                                    -(r["judged"] if isinstance(r["judged"], int) else 0),
                                    -int(r["candidates"]), str(r["producer"])))
    out["n_producers"] = len(ordered)
    out["producers"] = ordered
    out["certificates_unnamed"] = unnamed
    out["totals"] = {
        "certificates": len(live),
        "certificates_named": sum(int(r["certificates"]) for r in ordered),
        "producers_with_a_certificate": sum(1 for r in ordered if r["certificates"]),
        "candidates": sum(int(r["candidates"]) for r in ordered),
        "discoveries": sum(int(r["discoveries"]) for r in ordered),
        "docket": sum(int(r["docket"]) for r in ordered),
        "judged": sum(int(r["judged"]) for r in ordered if isinstance(r["judged"], int)),
        "judged_stamped": sum(int(r["judged_stamped"]) for r in ordered)}
    return out


def write(doc: dict[str, Any], budget_s: float = 300.0) -> dict[str, Any]:
    """Publish the birth record and the conversion table derived from it, in one pass so the two
    can never drift. Returns the table."""
    raw = doc.get("records")
    records: dict[str, Any] = dict(raw) if isinstance(raw, dict) else {}
    live = {c for c, r in records.items() if isinstance(r, dict) and r.get("in_canon")}
    _atomic(RECORD, {"at": doc.get("at"), "law": LAW, "rule": RULE,
                     "identity": doc.get("identity"),
                     "n_certificates": doc.get("n_certificates"),
                     "coverage": doc.get("coverage"), "routes": doc.get("routes"),
                     "keys": doc.get("keys"), "records": records})
    conn = None
    try:
        conn = sqlite3.connect(f"file:{REGISTRY}?mode=ro", uri=True)
    except sqlite3.Error:
        conn = None
    try:
        table = conversion(conn, records, live,
                           deadline=time.monotonic() + max(10.0, float(budget_s)))
    finally:
        if conn is not None:
            conn.close()
    table["coverage"] = doc.get("coverage")
    _atomic(TABLE, table)
    return table


def coverage_gate(record_doc: Any, certs: dict[str, dict[str, Any]]) -> tuple[int, str]:
    """THE FENCE: every certificate the store holds today has a birth-record row WITH a source
    lineage (UNMEASURED with its reason counts; no row does not). rc 1 on a shortfall.

    A record computed against a DIFFERENT store (its `keys` are not today's certificate keys) is
    STALE, not short: the organ has not run since the canon changed, which the hourly leg cures.
    That is reported UNMEASURED with rc 0 -- failing a gate over a clock that has not turned yet
    would fail every host that is not the box -- and a record that DID see today's store and
    still left a certificate without a row fails, because then the organ itself dropped it.
    """
    if not certs:
        return 0, f"{UNMEASURED}: no certificate store readable"
    if not isinstance(record_doc, dict) or not isinstance(record_doc.get("records"), dict):
        return 0, (f"{UNMEASURED}: no birth record at {RECORD.as_posix()}; "
                   "hourly_cycle:attribution_census writes it")
    records = record_doc["records"]
    want = {k: cell_of(k, r) for k, r in certs.items()}
    short = sorted(k for k, c in want.items()
                   if not isinstance(records.get(c), dict)
                   or not str(records[c].get("verdict") or "").strip()
                   or not isinstance(records[c].get("source_lineage"), dict))
    n = len(want)
    line = f"{n - len(short)}/{n} current certificates carry a birth record with a source lineage"
    seen = record_doc.get("keys")
    if isinstance(seen, dict) and set(seen) != set(want):
        return 0, (f"{UNMEASURED}: STALE -- the record was computed against {len(seen)} "
                   f"certificate keys, the store holds {n} ({len(set(want) - set(seen))} new); "
                   f"the organ has not run since the canon changed. {line}")
    if short:
        return 1, (f"FAIL: {line}; missing: {', '.join(short[:8])}"
                   + (f" (+{len(short) - 8} more)" if len(short) > 8 else ""))
    return 0, f"OK: {line}"


def render(doc: dict[str, Any], table: dict[str, Any] | None = None) -> list[str]:
    if not doc.get("records"):
        return [f"CERTIFICATE PROVENANCE  {doc.get('why') or 'no records'}"]
    cov = doc.get("coverage") or {}
    lines = [f"CERTIFICATE PROVENANCE  {doc.get('at')}",
             f"  certificates  {cov.get('n')}: named {cov.get('named')}, unnamed "
             f"{cov.get('unnamed')} (coverage {cov.get('coverage')})",
             f"  records       {cov.get('recorded')}/{cov.get('current_certificates')} current "
             f"certificates (record coverage {cov.get('record_coverage')})",
             f"  lineage       {json.dumps((cov.get('source_lineage') or {}).get('by_status'))} "
             f"ends at {json.dumps((cov.get('source_lineage') or {}).get('ends_at'))}",
             f"  verdicts      {json.dumps(cov.get('by_verdict'))}",
             f"  pending       {doc.get('pending')} of {doc.get('n_certificates')} "
             f"({doc.get('warm')} already final)"]
    for who, n in list((cov.get("by_producer") or {}).items())[:12]:
        lines.append(f"    {n:>4}  {who}")
    if table:
        t = table.get("totals") or {}
        lines.append(f"  conversion    {t.get('producers_with_a_certificate')} of "
                     f"{table.get('n_producers')} producers hold a certificate; "
                     f"{t.get('candidates')} candidates, {t.get('docket')} at the door, "
                     f"{t.get('judged')} judged, {t.get('certificates_named')} certificates named")
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="The birth record of every certificate, and the producer conversion table")
    ap.add_argument("--once", action="store_true", help="one pass (the only mode)")
    ap.add_argument("--budget-s", type=float, default=240.0)
    ap.add_argument("--retry-unmeasured", action="store_true",
                    help="re-run the routes for certificates already recorded UNMEASURED")
    ap.add_argument("--rebuild", action="store_true",
                    help="discard every prior record and re-join from the stores. For when the "
                         "RULE changed, never as routine: a certificate is immutable and its "
                         "record should not move under a reader who cited it")
    args = ap.parse_args(argv)
    doc = refresh(budget_s=float(args.budget_s), retry_unmeasured=bool(args.retry_unmeasured),
                  rebuild=bool(args.rebuild))
    table = write(doc, budget_s=float(args.budget_s)) if doc.get("records") else None
    for line in render(doc, table):
        print(line)
    return 0


if __name__ == "__main__":                                               # pragma: no cover
    raise SystemExit(main())
