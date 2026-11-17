"""The llm_lab cell compiler and donation writer: payload -> exact registered cell, novelty
processing, the donation row, the retry of conversion debt and the look-ahead guard.

Split out of `llm_lab.py` (2026-11-17) with `llm_lab_core.py`. The names a pass or a test
re-points on `llm_lab` (`_lane_ok`, `_series_present`, `MODEL_CUTOFFS`) are read off that module
at call time through `_lab()`, so re-pointing them there still reaches this code.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


from llm_lab_core import (  # noqa: E402,F401
    _BANAL,
    _NOVEL_ELEMENT,
    _SKIP_PARAMS,
    _STOP,
    _WORD,
    ASSET_CLASSES,
    BLOCKERS,
    CALLS,
    COLD_SHARE,
    COVERAGE,
    COVERAGE_STATES,
    DATA_REQUESTS,
    DEBT,
    EMITTED_CLASSES,
    EXOTIC_CAP,
    EXOTIC_CLASSES,
    EXOTIC_KEEP,
    FORMULA_GRAMMAR,
    GAP_CLASSES,
    GAP_NOTE,
    GAP_SHARE,
    GAUNTLET_PROBE,
    GENEALOGY,
    GRAMMAR,
    HORIZONS,
    INVENTORS,
    JEV_JOBS,
    LAB_BY_KEY,
    LABS,
    LANE_POLICY_ERRORS,
    LICENSE_OK,
    LITERATURE_DIRS,
    LITERATURE_FILES_PER_DIR,
    MECH_NEIGHBOUR_J,
    MODELS,
    NOVELTY_CLASSES,
    ONTOLOGY,
    ORGAN,
    PRIORITY_LABS,
    PROBE_CACHE_NAME,
    PROBE_TIMEOUT_S,
    REFEREE_GRAMMAR,
    REFEREE_MAX,
    REFEREE_TASK,
    REVISION_TASK,
    ROLE_LABS,
    ROTATION,
    RULE,
    STATE_DIR,
    TASK_RULES,
    UNIVERSE,
    UNMEASURED,
    UNMEASURED_TAG,
    WRAPPERS,
    YIELD_SHARE,
    Ask,
    Compiled,
    Coverage,
    FamilySpec,
    Lab,
    Memory,
    Tally,
    _append_jsonl,
    _calls_left,
    _cb_tone_role,
    _choose_coordinate,
    _coerce,
    _collector_role,
    _count_calls,
    _expr_ok,
    _h,
    _jsonl,
    _lane_ok,
    _local_license,
    _now,
    _ontology,
    _param_twin,
    _probe_gauntlet,
    _read_json,
    _rel,
    _resolve_symbols,
    _save_ontology,
    _seat,
    _series_present,
    _symbols_for,
    _validate,
    _validate_attack,
    _validate_referee,
    _write_json,
    all_family_names,
    assign_model,
    banal,
    breadth_gap,
    cell_identity,
    choose_coordinate,
    classify,
    converter_asks,
    coord_id,
    coordinates,
    enforce_exotic_cap,
    family_registry,
    hunt_models,
    jaccard,
    jev_series_name,
    market_share,
    menu_lines,
    observe_model,
    openrouter_pass_share,
    owed,
    prioritised,
    referee_model,
    referee_targets,
    registry_fingerprint,
    slug,
    synthesis_lines,
    tokens,
    universe,
)


def _lab() -> Any:
    """The live `llm_lab` module: the imported one, or `__main__` when the lab runs as a script."""
    mod = sys.modules.get("llm_lab")
    if mod is None:
        main = sys.modules.get("__main__")
        if main is not None and Path(getattr(main, "__file__", "") or "").name == "llm_lab.py":
            return main
        import llm_lab as mod
    return mod

def compile_payload(payload: dict[str, Any], reg: dict[str, FamilySpec],
                    uni: dict[str, str]) -> Compiled:
    """Turn one accepted proposal into exact cells, or name every blocker. Invents nothing."""
    out = Compiled()
    fam = str(payload.get("family") or "").strip()
    expr = str(payload.get("expr") or "").strip()
    syms, missing = _resolve_symbols(payload.get("symbols"), uni)
    if missing and not syms:
        out.blockers.append("NEEDS_INSTRUMENT_MAPPING")
        out.detail.append(f"no MT5 symbol for {missing[:4]}")
    if not syms and not missing:
        out.blockers.append("NEEDS_INSTRUMENT_MAPPING")
        out.detail.append("no instrument named")

    jq = payload.get("jev_question")
    if isinstance(jq, dict) and str(jq.get("question") or "").strip():
        q = str(jq["question"]).strip()[:300]
        out.jev_question = {"question": q, "answer_type": str(jq.get("answer_type") or
                                                              "probability")[:20],
                            "entities": [str(x)[:40] for x in (jq.get("entities") or [])][:8],
                            "horizon": str(payload.get("horizon") or "")[:20],
            "literature": [str(u)[:160] for u in payload.get("literature") or []][:5],
            "competing_explanations": [str(c)[:240] for c in
                                       payload.get("competing_explanations") or []][:4],
            "separating_test": str(payload.get("separating_test") or "")[:200],
                            "series": jev_series_name(q)}
        if not fam:
            fam = "exogenous_conditioner"
            params_in = dict(payload.get("params") or {})
            params_in.setdefault("source", out.jev_question["series"])
            params_in.setdefault("signal", "p")
            payload = {**payload, "family": fam, "params": params_in}

    if not fam or fam.upper() in ("NONE", "NEW", "UNIMPLEMENTED"):
        if expr:
            fam = "formula"
        else:
            out.blockers.append("NEEDS_EXECUTABLE_FAMILY")
            out.detail.append("no registered family expresses this mechanism yet")
            return out
    try:
        from family_policy import family_banned
    except ImportError:                                # pragma: no cover
        def family_banned(_f: object) -> bool:          # type: ignore[misc]
            return False
    if family_banned(fam):
        out.refused = f"BANNED_FAMILY:{fam}"
        return out
    spec = reg.get(fam)
    if spec is None:
        out.blockers.append("NEEDS_EXECUTABLE_FAMILY")
        out.detail.append(f"family {fam!r} is not registered")
        return out

    raw = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    params: dict[str, Any] = {}
    dropped = []
    for k, v in raw.items():
        if k not in spec.params:
            dropped.append(k)
            continue
        try:
            params[k] = _coerce(v, spec.params[k])
        except (TypeError, ValueError):
            out.blockers.append("NEEDS_PARAMETER_INFERENCE")
            out.detail.append(f"{fam}.{k}={str(v)[:30]!r} is not a {type(spec.params[k]).__name__}")
    if dropped:
        out.detail.append(f"ignored keys outside {fam}'s signature: {dropped[:6]}")
    if fam == "formula":
        canon, why = _expr_ok(expr or str(params.get("expr") or ""))
        if not canon:
            out.blockers.append("NEEDS_EXACT_RULE_EXTRACTION")
            out.detail.append(why)
        else:
            params["expr"] = canon
    for key in ("base_family",):
        if key in spec.params and params.get(key) and params[key] not in reg:
            out.blockers.append("NEEDS_EXECUTABLE_FAMILY")
            out.detail.append(f"base_family {params[key]!r} is not registered")
    if "source" in spec.params and fam in ("exogenous_conditioner", "alt_conditioned",
                                           "alt_series_momentum"):
        src = str(params.get("source") or "")
        if not src:
            out.blockers.append("NEEDS_PIT_SOURCE")
            out.detail.append(f"{fam} names no source series")
        elif not _lab()._series_present(src):
            out.blockers.append("NEEDS_DATA")
            out.data_needed.append(src)
            out.detail.append(f"series {src!r} is not in the lake on this host")
    tf = str(payload.get("timeframe") or "").upper()
    if tf in ("M5", "M15", "M30", "H1", "H4", "D1"):
        params.setdefault("timeframe", tf)
    if out.blockers:
        out.blockers = list(dict.fromkeys(out.blockers))
        return out
    refused_lane = []
    for s in syms:
        if not _lab()._lane_ok(s, fam):
            refused_lane.append(s)
            continue
        out.cells.append({"symbol": s, "family": fam, "params": dict(params)})
    if refused_lane and not out.cells:
        out.refused = f"LANE_REFUSED:{fam}:{refused_lane[:4]}"
    return out


def process(prop: Any, lab_key: str, coord: dict[str, str], reg: dict[str, FamilySpec],
            uni: dict[str, str], mem: Memory, tally: Tally, models: dict[str, Any],
            outputs: dict[str, list[dict[str, Any]]]) -> None:
    """One proposal to exactly one disposition, recorded in the genealogy."""
    model = str(getattr(prop.provenance, "model", "") or "")
    mrow = models.get(model)
    tally.proposals += 1
    if not prop.accepted:
        tally.discarded += 1
        tally.reasons[str(prop.reason)[:80]] += 1
        return
    tally.accepted += 1
    if mrow is not None:
        mrow["accepted"] = int(mrow.get("accepted", 0)) + 1
    payload = dict(prop.payload)
    mech = str(payload.get("mechanism") or "")[:400]
    mclass = slug(payload.get("mechanism_class") or coord["mechanism_class"]) or "unnamed"
    pkey = json.dumps(payload.get("params"), sort_keys=True, default=str)
    node = f"LLMLAB-{_h(lab_key, mech, pkey)}"
    base_row = {"node": node, "lab": lab_key, "at": _now(), "model": model,
                "prompt_hash": getattr(prop.provenance, "prompt_hash", ""),
                "coordinate": coord, "mechanism_class": mclass, "mechanism": mech,
                "falsifier": str(payload.get("falsifier") or "")[:300],
                "parents": [str(p) for p in payload.get("parents") or []][:6],
                "stripped": list(getattr(prop, "stripped", ()) or ())}
    outputs["classes"].append({"class": mclass, "lab": lab_key})
    b = banal(payload)
    if b:
        tally.banal += 1
        outputs["genealogy"].append({**base_row, "disposition": "BANAL_BASELINE", "baseline": b})
        return
    comp = compile_payload(payload, reg, uni)
    if comp.jev_question:
        outputs["jev"].append({**comp.jev_question, "node": node, "lab": lab_key,
                               "state": "QUEUED", "at": _now(),
                               # A Jev answer series labelled over historical text inherits the
                               # labelling model's cutoff, set when the job is answered.
                               "lookahead_guard": "set from the answering model's cutoff"})
    if comp.refused:
        tally.refused += 1
        outputs["genealogy"].append({**base_row, "disposition": "REFUSED", "why": comp.refused})
        return
    if comp.blockers:
        tally.debt += 1
        for bl in comp.blockers:
            tally.blockers[bl] += 1
        for src in comp.data_needed:
            outputs["data_requests"].append({"series": src, "node": node, "lab": lab_key,
                                             "mechanism": mech[:200], "at": _now()})
        outputs["debt"].append({"id": node, "lab": lab_key, "payload": payload,
                                "blockers": comp.blockers, "detail": comp.detail[:6],
                                "coordinate": coord, "first_seen": _now(), "attempts": 0,
                                "state": "OPEN"})
        outputs["genealogy"].append({**base_row, "disposition": "CONVERSION_DEBT",
                                     "blockers": comp.blockers, "detail": comp.detail[:6]})
        return
    for cell in comp.cells:
        cid = cell_identity(cell)
        klass, against = classify(cell, mech, base_row["parents"], mem)
        tally.novelty[klass] += 1
        g = {**base_row, "cell": cell, "cell_id": cid, "novelty_class": klass,
             "measured_against": against}
        if klass in EMITTED_CLASSES:
            tally.emitted += 1
            if mrow is not None:
                mrow["exact"] = int(mrow.get("exact", 0)) + 1
                mrow["novel"] = int(mrow.get("novel", 0)) + int(klass == "GENUINELY_NOVEL")
            outputs["donate"].append(donation_row(cell, cid, g, payload))
            g["disposition"] = "EMITTED"
        else:
            g["disposition"] = klass
        outputs["genealogy"].append(g)
        mem.remember(g)


def donation_row(cell: dict[str, Any], cid: str, g: dict[str, Any],
                 payload: dict[str, Any]) -> dict[str, Any]:
    """The exact shape `miner_candidate_compiler.compile_row` admits as EXACT_RECIPE."""
    return {"kind": "hypothesis", "family": cell["family"], "params": cell["params"],
            "symbols": [cell["symbol"]], "symbol": cell["symbol"],
            "mechanism": g["mechanism"], "falsifier": g["falsifier"],
            "title": (f"{'[ORIG] ' if g['novelty_class'] == 'GENUINELY_NOVEL' else ''}"
                      f"llm_lab {g['lab']}: {g['mechanism'][:120]}"),
            "orig": g["novelty_class"] == "GENUINELY_NOVEL",
            "breadth_gap": breadth_gap(cell["symbol"], payload),
            "lab": g["lab"], "lab_name": LAB_BY_KEY[g["lab"]].name if g["lab"] in LAB_BY_KEY
            else g["lab"], "novelty_class": g["novelty_class"], "cell_id": cid,
            "genealogy": {"node": g["node"], "parents": g["parents"],
                          "measured_against": g["measured_against"]},
            "lineage": {"root": g["node"], "operator": "llm_lab"},
            "mechanism_class": g["mechanism_class"], "coordinate": g["coordinate"],
            "model": g["model"], "prompt_hash": g["prompt_hash"],
            "horizon": str(payload.get("horizon") or "")[:20],
            "literature": [str(u)[:160] for u in payload.get("literature") or []][:5],
            "competing_explanations": [str(c)[:240] for c in
                                       payload.get("competing_explanations") or []][:4],
            "separating_test": str(payload.get("separating_test") or "")[:200],
            "url": f"llm_lab://{g['lab']}/{g['node']}",
            "lookahead_guard": lookahead_guard(g["model"]),
            "copy_trade": False, "credibility_inherited": False, "gauntlet_bypass": False}


def lookahead_guard(model: str, *, at: str | None = None) -> dict[str, Any]:
    """THE LOOK-AHEAD GUARD (2026-10-13). A model that proposed or labelled a cell has READ the
    history the cell is about to be backtested on: anything before its training cutoff is
    contaminated -- the cell may go to the gauntlet, but that window is not evidence.

    `evidence_from` is the LATER of the model's documented cutoff and the date the cell was born
    (audit must-fix 2, 2026-10-13: it was the earlier, so a 2023-12-01 cutoff let 34 months the
    model had seen count). Only data after both counts: the model has not read it, and the cell
    was not shaped by it. With no registered cutoff it is the birth date, so ONLY forward
    (post-generation) data is evidence -- which the forward clocks already require before any
    promotion, so the guard tightens nothing that is live and loosens nothing.
    """
    day = (at or _now())[:10]
    table = _read_json(_lab().MODEL_CUTOFFS, {}) or {}
    hit = next((str(d)[:10] for frag, d in table.items()
                if isinstance(frag, str) and frag and frag.lower() in model.lower()), "")
    return {"model": model, "model_training_cutoff": hit or UNMEASURED,
            "evidence_from": max(hit, day) if hit else day,
            "basis": ("registered cutoff" if hit else
                      "cutoff UNMEASURED: generation date, so only post-generation data counts"),
            "rule": "backtest data before evidence_from is contaminated; it may be run, never "
                    "counted as evidence"}


def retry_debt(reg: dict[str, FamilySpec], uni: dict[str, str], mem: Memory, tally: Tally,
               outputs: dict[str, list[dict[str, Any]]], fingerprint: str,
               limit: int = 400, write: bool = True) -> dict[str, Any]:
    """TEMPORAL REOPENING: every open debt is re-compiled when the families, the universe or the
    lake could have changed. Deterministic, no model call, bounded per pass by a rotating cursor."""
    doc = _read_json(DEBT, {}) or {}
    rows: dict[str, dict[str, Any]] = doc.get("rows") or {}
    opened = [r for r in rows.values() if r.get("state") == "OPEN"]
    opened.sort(key=lambda r: (str(r.get("last_attempt") or ""), str(r.get("first_seen") or "")))
    resolved = 0
    for r in opened[:limit]:
        r["attempts"] = int(r.get("attempts", 0)) + 1
        r["last_attempt"] = _now()
        comp = compile_payload(dict(r.get("payload") or {}), reg, uni)
        if comp.cells and not comp.blockers:
            r["state"] = "RESOLVED"
            r["resolved_at"] = _now()
            resolved += 1
            for cell in comp.cells:
                cid = cell_identity(cell)
                mech = str((r.get("payload") or {}).get("mechanism") or "")[:400]
                klass, against = classify(cell, mech, [], mem)
                g = {"node": r["id"], "lab": r.get("lab"), "at": _now(), "model": "debt_reopen",
                     "prompt_hash": "", "coordinate": r.get("coordinate") or {},
                     "mechanism_class": slug((r.get("payload") or {}).get("mechanism_class")
                                             or "reopened"),
                     "mechanism": mech, "falsifier": str((r.get("payload") or {})
                                                         .get("falsifier") or "")[:300],
                     "parents": [], "cell": cell, "cell_id": cid, "novelty_class": klass,
                     "measured_against": against}
                tally.novelty[klass] += 1
                if klass in EMITTED_CLASSES:
                    tally.emitted += 1
                    outputs["donate"].append(donation_row(cell, cid, g, r.get("payload") or {}))
                    g["disposition"] = "EMITTED"
                else:
                    g["disposition"] = klass
                outputs["genealogy"].append(g)
                mem.remember(g)
        else:
            r["blockers"] = comp.blockers or r.get("blockers") or []
            r["detail"] = comp.detail[:6] or r.get("detail") or []
            if comp.refused:
                r["state"] = "REFUSED"
                r["why"] = comp.refused
    for d in outputs["debt"]:
        rows.setdefault(d["id"], d)
    doc["rows"] = rows
    doc["fingerprint"] = fingerprint
    if write:
        _write_json(DEBT, doc)
    open_rows = [r for r in rows.values() if r.get("state") == "OPEN"]
    by = Counter(b for r in open_rows for b in r.get("blockers") or [])
    return {"open": len(open_rows), "resolved_this_pass": resolved,
            "retried_this_pass": min(limit, len(opened)), "by_blocker": dict(by),
            "rule_shaped_open": [r["id"] for r in open_rows
                                 if set(r.get("blockers") or []) & {
                                     "NEEDS_EXACT_RULE_EXTRACTION", "NEEDS_PARAMETER_INFERENCE",
                                     "NEEDS_EXECUTABLE_FAMILY"}][:50]}

