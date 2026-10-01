"""The pre-registration join, run by the docket writer every hour: cards before, verdicts after.

`merge_hypotheses` is the one funnel the judge's input flows through, and it runs on the hour
BEFORE the judge reads the docket. So it is where both halves of pre-registration belong:

  1. BEFORE judgement: `preregistration.register_docket` stamps every docket row with the card
     that fixes its exact spec, writing one batch card for every never-judged cell that has
     none. A cell the desk already judged gets RETROSPECTIVELY_UNPREREGISTERED and no card.
  2. AFTER judgement: `record_gate_ledger` reads what the judge appended to
     `gate_verdict_ledger.jsonl` since the last pass, stamps each verdict POST_HOC or
     PREREGISTERED, and records its fate on the hypothesis graph -- the writer the graph never
     had (every FAILED / CERTIFIED fate it holds came from a hand-run backfill, last 2026-09-03).

A judge that stamps its own verdicts (the gate-ledger row then carries `prereg_status`) has
already recorded them in-process, so step 2 skips those rows: one verdict, one graph writer.
"""
from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any

from libs.research import hypothesis_graph as hg
from libs.research import preregistration as pr

ROOT = Path(__file__).resolve().parents[2]
HYP = ROOT / "desks" / "mt5" / "data" / "hypotheses"
GATE_LEDGER = HYP / "gate_verdict_ledger.jsonl"
SEEN_CELLS = HYP / "gauntlet_seen_cells.json"
#: Runtime state (a byte offset), never a record: losing it costs one re-read, and the graph
#: writer is change-only, so a re-read appends nothing.
CURSOR = HYP / "prereg_join_cursor.json"


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None


def _ledger_rows(path: Path, start: int = 0) -> tuple[list[dict[str, Any]], int]:
    """Rows from byte `start` to the end, and the new end. A ledger shorter than the cursor was
    rotated or rewritten, so it is re-read from the top (harmless: the writer is change-only)."""
    try:
        size = path.stat().st_size
    except OSError:
        return [], 0
    if start > size:
        start = 0
    rows: list[dict[str, Any]] = []
    with path.open("rb") as fh:
        fh.seek(start)
        data = fh.read()
    end = start + len(data)
    for ln in data.decode("utf-8", errors="replace").splitlines():
        if not ln.strip():
            continue
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if isinstance(r, dict):
            rows.append(r)
    return rows, end


def judged_spec_ids(graph: hg.Graph, *, gate_ledger: Path = GATE_LEDGER) -> set[str]:
    """Every spec id the desk has EVER judged: graph fates plus the gate ledger's `graph_id`."""
    out = {str(r.get("id")) for r in graph.rows()
           if r.get("fate") in (hg.FAILED, hg.CERTIFIED, hg.JUDGED)}
    rows, _ = _ledger_rows(gate_ledger)
    out.update(str(r["graph_id"]) for r in rows if r.get("graph_id"))
    return out


def preregister_docket(rows: list[dict[str, Any]], *, graph: hg.Graph | None = None,
                       gate_ledger: Path = GATE_LEDGER, seen_cells: Path = SEEN_CELLS,
                       cell_id: Callable[[dict[str, Any]], str] | None = None,
                       prereg_path: Path | None = None) -> dict[str, Any]:
    """Step 1. `cell_id` names a spec the way the judge's first-seen stamps do, so a cell judged
    before either the graph or the gate ledger knew it still counts as judged."""
    g = graph or hg.Graph()
    judged = judged_spec_ids(g, gate_ledger=gate_ledger)
    seen = _read_json(seen_cells)
    if isinstance(seen, dict) and seen and cell_id is not None:
        for r in rows:
            spec = pr.judged_spec(r) if isinstance(r, dict) else None
            if spec is None:
                continue
            try:
                if cell_id(spec) in seen:
                    judged.add(hg.node_id_for_spec(spec))
            except (KeyError, TypeError, ValueError):
                continue
    return pr.register_docket(rows, judged=judged, path=prereg_path)


def _verdict_of(row: Mapping[str, Any]) -> dict[str, Any]:
    """A gate-ledger row back into the verdict shape the graph writer reads.

    The ledger stores `passed` as a bool and an unmeasured outcome as terminal gate UNKNOWN, so
    UNKNOWN reads back as `passed: None` with a stage that says so (a JUDGED fate), never as a
    failure the judge did not report.
    """
    unknown = str(row.get("terminal_gate") or "") == "UNKNOWN"
    passed = None if unknown else bool(row.get("passed"))
    return {"cell": row.get("cell"), "sym": row.get("sym"), "family": row.get("family"),
            "passed": passed, "terminal_gate": row.get("terminal_gate"),
            "spec_id": row.get("graph_id") or None, "hunt": "gauntlet", "at": row.get("at"),
            "stages": {"gate_ledger": {"passed": passed,
                                       "downstream_status": row.get("downstream_status")}}}


def record_gate_ledger(*, graph: hg.Graph | None = None, gate_ledger: Path = GATE_LEDGER,
                       cursor: Path = CURSOR, seen_cells: Path = SEEN_CELLS,
                       specs: Iterable[Mapping[str, Any]] = (),
                       prereg_path: Path | None = None) -> dict[str, Any]:
    """Step 2. `specs` is any iterable of rows carrying symbol/family/params (the docket); the
    graph's own BORN rows are read too, so a verdict whose params the compiler registered
    resolves even when the docket has moved on. A verdict that resolves to no params is stamped
    and COUNTED as `no_spec`, never recorded under a guessed id."""
    g = graph or hg.Graph()
    doc = _read_json(cursor)
    start = int(doc.get("offset") or 0) if isinstance(doc, dict) else 0
    rows, end = _ledger_rows(gate_ledger, start)
    out: dict[str, Any] = {"ledger": str(gate_ledger), "from_offset": start, "to_offset": end,
                           "rows": len(rows), "stamped_by_judge": 0}
    if not gate_ledger.exists():
        out["status"] = "UNMEASURED: no gate-verdict ledger on this host"
        return out
    pending: list[dict[str, Any]] = []
    for r in rows:
        if r.get("prereg_status"):
            out["stamped_by_judge"] += 1       # the judge recorded it in-process already
            continue
        pending.append(_verdict_of(r))
    by_id: dict[str, dict[str, Any]] = {}
    want = {str(v["spec_id"]) for v in pending if v.get("spec_id")}
    if want:
        for s in specs:
            spec = pr.judged_spec(s) if isinstance(s, Mapping) else None
            if spec is not None:
                sid = hg.node_id_for_spec(spec)
                if sid in want:
                    by_id.setdefault(sid, spec)
        for nid, row in g.current().items():
            if nid in want and nid not in by_id and isinstance(row.get("params"), dict):
                by_id[nid] = {"sym": row.get("symbol"), "family": row.get("family"),
                              "params": row.get("params")}
    specs_by_cell = {str(v["cell"]): by_id[str(v["spec_id"])] for v in pending
                     if v.get("spec_id") and str(v["spec_id"]) in by_id and v.get("cell")}
    first: dict[str, str] = {}
    seen = _read_json(seen_cells)
    if isinstance(seen, dict):
        first.update({str(k): str(t) for k, t in seen.items()})
    all_rows, _ = _ledger_rows(gate_ledger)
    for r in all_rows:
        c, t = str(r.get("cell") or ""), str(r.get("at") or "")
        if c and t and (c not in first or t < first[c]):
            first[c] = t
    res = hg.record_gauntlet_verdicts(pending, specs_by_cell, first_judged=first, graph=g,
                                      prereg_path=prereg_path)
    out.update(res)
    try:
        cursor.parent.mkdir(parents=True, exist_ok=True)
        cursor.write_text(json.dumps({"offset": end}), "utf-8")
    except OSError as exc:
        out["cursor_error"] = f"{type(exc).__name__}: {exc}"
    out["status"] = "MEASURED"
    return out
