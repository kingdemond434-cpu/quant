"""LLM LAB ROUTING -- freeze, novelty, typed routing, requests, coverage debt and feedback.

  * FREEZE + NOVELTY + GENEALOGY: every candidate is hashed FROZEN_PRE_EVALUATION; exact
    duplicates collapse, parameter neighbours share one trial family, descendants keep parents.
  * TYPED ROUTING into the SAME stores: exact candidates -> `data/intelligence/deepseek`
    (compiler EXACT_RECIPE -> docket -> gauntlet); hypotheses -> the deepening door; data and
    source requests -> the hunt frontier (NAMED_ONLY) and an open-request ledger that re-checks
    arrival; capability challengers -> the existing walk.
  * COVERAGE DEBT: an exact candidate's same-asset-class translations are owed coordinates,
    drained once the parent has a gauntlet verdict; a cap means "not this pass", never "never".
  * FEEDBACK: compiler receipts and gate-ledger verdicts are joined back by hypothesis id and
    credited to lab, model, family and prompt version.
"""
from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

from libs.ops import deepseek_cycle as ds
from libs.ops.llm_lab_core import (
    ATTRIBUTION,
    COMPILER_OUT,
    DEBT,
    FRONTIER,
    FROZEN,
    FROZEN_FIELDS,
    GATE_LEDGER,
    GATE_TAIL,
    REQUESTS,
    SCHEMA_VERSION,
    _append,
    _iso,
    _jaccard,
    _load,
    _now_dt,
    _save,
    _sha,
    _tokens,
    enqueue,
    load_memory,
)
from libs.ops.llm_lab_seats import (
    model_family,
)

# ---------------------------------------------------- freeze, novelty and genealogy


def _frozen_view(o: dict[str, Any]) -> dict[str, Any]:
    v = {k: o.get(k) for k in FROZEN_FIELDS if o.get(k) not in (None, "", [], {})}
    v["symbols"] = sorted(v.get("symbols") or [])
    return v


def novelty(o: dict[str, Any], memory: list[dict[str, Any]]) -> dict[str, Any]:
    """Section 15. Compared against every frozen DeepSeek hypothesis before anything is tested.

    EXACT_DUPLICATE        same frozen rules (any lab, any model): one discovery, not two
    CROSS_ASSET_TRANSLATION same family + params, other symbols: same trial family
    PARAMETER_NEIGHBOUR    same family + symbols + mechanism class, other params: same family
    MECHANISM_NEIGHBOUR    mechanism wording overlaps >= 0.55 (Jaccard on content tokens)
    COMPOSITIONAL_DESCENDANT names parents
    GENUINELY_NOVEL        none of the above"""
    fv = _frozen_view(o)
    rule_sig = _sha(fv)
    fam = str(o.get("family") or "")
    fp_sig = _sha([fam, o.get("params")]) if fam else None
    nb_sig = _sha([fam, sorted(o.get("symbols") or []), str(o.get("mechanism_class") or "")]) \
        if fam else None
    toks = _tokens(f"{o.get('economic_mechanism') or o.get('mechanism') or ''} "
                   f"{o.get('forced_actor') or ''} {o.get('title') or ''}")
    best, best_sim = None, 0.0
    for m in memory:
        if m.get("rule_sig") == rule_sig and fv.get("family"):
            return {"class": "EXACT_DUPLICATE", "of": m["hypothesis_id"],
                    "trial_family_id": m.get("trial_family_id"), "rule_sig": rule_sig}
        if fp_sig and m.get("fp_sig") == fp_sig:
            return {"class": "CROSS_ASSET_TRANSLATION", "of": m["hypothesis_id"],
                    "trial_family_id": m.get("trial_family_id"), "rule_sig": rule_sig}
        if nb_sig and m.get("nb_sig") == nb_sig:
            return {"class": "PARAMETER_NEIGHBOUR", "of": m["hypothesis_id"],
                    "trial_family_id": m.get("trial_family_id"), "rule_sig": rule_sig}
        sim = _jaccard(toks, set(m.get("tokens") or []))
        if sim > best_sim:
            best, best_sim = m, sim
    if best is not None and best_sim >= 0.55:
        return {"class": "MECHANISM_NEIGHBOUR", "of": best["hypothesis_id"],
                "similarity": round(best_sim, 3),
                "trial_family_id": best.get("trial_family_id"), "rule_sig": rule_sig}
    parents = [p for p in (o.get("parent_ids") or []) if isinstance(p, str) and p]
    tf = "dstf_" + _sha([fam, sorted(toks)[:24]], 16)
    return {"class": "COMPOSITIONAL_DESCENDANT" if parents else "GENUINELY_NOVEL",
            "of": parents[0] if parents else None, "trial_family_id": tf, "rule_sig": rule_sig,
            "nearest_similarity": round(best_sim, 3)}


def freeze(root: Path, o: dict[str, Any], nov: dict[str, Any], prov: dict[str, Any]
           ) -> dict[str, Any]:
    """FROZEN_PRE_EVALUATION (section 24). The id IS the hash of the frozen rules, so a later edit
    is a new hypothesis by construction; the frozen view is written before any routing."""
    fv = _frozen_view(o)
    hid = "dsh_" + _sha(fv)
    fam = str(o.get("family") or "")
    row = {"hypothesis_id": hid, "frozen_hash": _sha(fv, 64), "frozen": fv,
           "status": "FROZEN_PRE_EVALUATION", "frozen_utc": _iso(_now_dt()),
           "rule_sig": nov["rule_sig"],
           "fp_sig": _sha([fam, o.get("params")]) if fam else None,
           "nb_sig": _sha([fam, sorted(o.get("symbols") or []),
                           str(o.get("mechanism_class") or "")]) if fam else None,
           "tokens": sorted(_tokens(f"{o.get('economic_mechanism') or o.get('mechanism') or ''} "
                                    f"{o.get('forced_actor') or ''} {o.get('title') or ''}"))[:64],
           "trial_family_id": nov.get("trial_family_id"),
           "parent_ids": [p for p in (o.get("parent_ids") or []) if isinstance(p, str)],
           "novelty": nov["class"], "object_type": o["object_type"],
           "disposition": o["disposition"], **prov}
    _append(root / FROZEN, row)
    return row


# ---------------------------------------------------------------------------- routing


def _donation_row(o: dict[str, Any], hid: str, tfid: str | None, lab: str) -> dict[str, Any]:
    params = dict(o.get("params") or {}) if isinstance(o.get("params"), dict) else None
    if params is not None:
        for axis in ("timeframe", "session"):
            if o.get(axis) and axis not in params and str(o.get(axis)).lower() not in ("all", "h1"):
                params[axis] = o[axis]
    row = {"source": "deepseek", "title": str(o.get("title") or "")[:300],
           "symbols": o.get("symbols") or [], "type": o["object_type"],
           "disposition": o["disposition"], "family": o.get("family"),
           "mechanism": str(o.get("economic_mechanism") or o.get("mechanism") or "")[:2000],
           "testable_claim": str(o.get("falsifier") or o.get("testable_claim") or "")[:2000],
           "entry_rule": o.get("entry_rule"), "exit_rule": o.get("exit_rule"),
           "stop_rule": o.get("stop_rule"), "holding_horizon": o.get("holding_horizon"),
           "mechanism_tags": [t for t in [o.get("family"), o.get("mechanism_class")] if t],
           "kind": "exact_recipe" if o["disposition"] == "TESTABLE_NOW" else "hypothesis",
           "url": f"deepseek://{lab}/{hid}", "hypothesis_id": hid,
           "lineage": {"root": hid, "trial_family_id": tfid,
                       "parents": [p for p in (o.get("parent_ids") or []) if isinstance(p, str)]}}
    if params is not None and o["disposition"] == "TESTABLE_NOW":
        row["params"] = params
    if o.get("parent_ids"):
        row["parent_ids"] = o["parent_ids"]
    return row


def donate(root: Path, rows: list[dict[str, Any]], tag: str) -> Path | None:
    """Into `data/intelligence/deepseek/` -- the tree `miner_candidate_compiler` reads -- in the
    miner-discovery contract, PIT-stamped by the shared stamper. No new admission path."""
    if not rows:
        return None
    from libs.data.pit import stamp_or_refuse
    stamped, refused = stamp_or_refuse(rows, "deepseek")
    if refused:
        raise ValueError(f"DeepSeek refused {len(refused)} unstamped discoveries")
    out = root / ds.DONATE_DIR
    out.mkdir(parents=True, exist_ok=True)
    stamp = _iso(_now_dt()).replace(":", "").replace("-", "")[:15]
    path = out / f"discoveries_{stamp}_{_sha(tag, 6)}.json"
    _save(path, {"source": "deepseek", "lab_tag": tag, "schema_version": SCHEMA_VERSION,
                 "generated_at": _iso(_now_dt()), "discoveries": stamped})
    return path


def _requests(root: Path) -> dict[str, Any]:
    r = _load(root / REQUESTS, {})
    if not isinstance(r, dict) or not isinstance(r.get("open"), dict):
        r = {"open": {}, "closed": {}}
    return r


def file_request(root: Path, o: dict[str, Any], prov: dict[str, Any]) -> str:
    """DATA / SOURCE / REPRESENTATION requests and VALIDATION ATTACKS: an open ledger that the
    lab re-checks every cycle (arrival closes a data request and resumes its parent), plus, for
    data and sources, a NAMED_ONLY vector on the hunt frontier -- which the hunters treat as
    priority ground, never as covered."""
    reqs = _requests(root)
    t = o["object_type"]
    key = str(o.get("variable") or o.get("representation") or o.get("target") or
              o.get("source") or o.get("title") or "").strip()
    rid = "dsr_" + _sha([t, key.lower()], 14)
    if rid not in reqs["open"] and rid not in reqs["closed"]:
        reqs["open"][rid] = {"request_id": rid, "object_type": t, "key": key[:200],
                             "title": str(o.get("title") or key)[:300],
                             "mechanism": str(o.get("mechanism") or o.get("economic_mechanism")
                                              or "")[:1000],
                             "falsifier": str(o.get("falsifier") or "")[:500],
                             "source_classes": o.get("source_classes") or o.get("source"),
                             "pit_requirements": o.get("pit_requirements"),
                             "attack": o.get("attack"), "test": o.get("cheapest_decisive_test"),
                             "parent_hypothesis": o.get("parent_hypothesis"),
                             "opened_utc": _iso(_now_dt()), "status": "OPEN", **prov}
    elif rid in reqs["open"] and o.get("parent_hypothesis"):
        reqs["open"][rid].setdefault("also_for", []).append(o["parent_hypothesis"])
    _save(root / REQUESTS, reqs)
    if t in ("DATA_REQUEST", "SOURCE_ACQUISITION_REQUEST") and key:
        try:
            from libs.research import hunt_frontier as hf
            path = root / FRONTIER
            st = hf.load(path)
            name = f"deepseek data request: {key}"[:160]
            if name not in st.vectors:
                hf.record(st, name, outcome="NAMED_ONLY", region="deepseek_data_request")
                hf.save(st, path)
        except Exception:
            pass
    return rid


def recheck_requests(root: Path, series: set[str], q: dict[str, Any]) -> list[str]:
    """Section 11: data arrives -> conversion resumes. A data request whose variable now names a
    series the desk supplies is CLOSED and its parent hypotheses get a resume job."""
    reqs = _requests(root)
    closed = []
    for rid, r in list(reqs["open"].items()):
        if r.get("object_type") != "DATA_REQUEST":
            continue
        if str(r.get("key") or "").lower() in series:
            r["status"], r["closed_utc"] = "ARRIVED", _iso(_now_dt())
            reqs["closed"][rid] = reqs["open"].pop(rid)
            for parent in [r.get("parent_hypothesis"), *(r.get("also_for") or [])]:
                if parent:
                    enqueue(q, "CONV", f"resume:{parent}", {"hypothesis_id": parent,
                                                           "arrived": r.get("key")})
            closed.append(rid)
    if closed:
        _save(root / REQUESTS, reqs)
    return closed


def register_debt(root: Path, o: dict[str, Any], hid: str, tfid: str | None,
                  uni: dict[str, str]) -> int:
    """Section 13. The same exact rule on every other registry symbol of its asset class is an
    OWED coordinate with a stable id. Registering costs nothing; draining is capped per pass."""
    debt = _load(root / DEBT, {})
    if not isinstance(debt, dict) or not isinstance(debt.get("coords"), dict):
        debt = {"coords": {}}
    syms = set(o.get("symbols") or [])
    classes = {uni.get(s) for s in syms} - {None, "unknown"}
    n = 0
    for sym, cls in sorted(uni.items()):
        if cls not in classes or sym in syms:
            continue
        cid = "dsc_" + _sha([hid, sym], 16)
        if cid in debt["coords"]:
            continue
        debt["coords"][cid] = {"coord_id": cid, "parent": hid, "trial_family_id": tfid,
                               "symbol": sym, "family": o.get("family"),
                               "params": o.get("params"), "title": o.get("title"),
                               "mechanism": o.get("economic_mechanism"),
                               "status": "OWED", "registered_utc": _iso(_now_dt())}
        n += 1
    _save(root / DEBT, debt)
    return n


def drain_debt(root: Path, limit: int) -> dict[str, Any]:
    """Donate up to `limit` owed translations. The rest stay OWED -- a cap is 'not this pass',
    never 'never'.

    ORDER IS THE ECONOMICS. A translation is worth judging once its PARENT has a gauntlet verdict:
    a passed parent's translations go first (where else does the mechanism pay?), a judged-failed
    parent's next (does it fail everywhere, or only there?), and an unjudged parent's wait --
    twenty-eight cells for an idea nobody has tested yet would spend the judge, the binding
    bottleneck, on the cheapest-to-defer work. Waiting coordinates are counted, never dropped."""
    debt = _load(root / DEBT, {})
    coords = debt.get("coords") if isinstance(debt, dict) else None
    if not isinstance(coords, dict):
        return {"owed": 0, "donated": 0, "awaiting_parent_verdict": 0}
    verdicts = ((_load(root / ATTRIBUTION, {}).get("gauntlet") or {}).get("verdicts") or {})
    owed_all = [c for c in coords.values() if c.get("status") == "OWED"]
    ready = [c for c in owed_all if c.get("parent") in verdicts]
    ready.sort(key=lambda c: (-int(bool((verdicts.get(c["parent"]) or {}).get("passed"))),
                              c.get("registered_utc") or "", c["coord_id"]))
    owed = ready
    rows = []
    for c in owed[:max(0, limit)]:
        rows.append({"source": "deepseek", "title": f"{c.get('title')} [{c['symbol']}]"[:300],
                     "symbols": [c["symbol"]], "family": c.get("family"),
                     "params": c.get("params") or {}, "type": "EXACT_CANDIDATE",
                     "disposition": "TESTABLE_NOW", "kind": "exact_recipe",
                     "mechanism": str(c.get("mechanism") or "")[:2000],
                     "operator": "cross_asset_translation",
                     "url": f"deepseek://debt/{c['parent']}/{c['coord_id']}",
                     "hypothesis_id": c["parent"],
                     "lineage": {"root": c["parent"], "trial_family_id": c.get("trial_family_id"),
                                 "parents": [c["parent"]], "operator": "cross_asset_translation"}})
        c["status"], c["donated_utc"] = "DONATED", _iso(_now_dt())
    path = donate(root, rows, "coverage_debt") if rows else None
    _save(root / DEBT, debt)
    left = len(owed) - len(rows)
    return {"owed": len(owed_all) - len(rows), "donated": len(rows),
            "awaiting_parent_verdict": len(owed_all) - len(ready),
            "path": str(path) if path else None,
            "drain_cycles_at_this_rate": (math.ceil(left / limit) if limit > 0 else None)}


def route(root: Path, recs: list[dict[str, Any]], *, lab: str, prov: dict[str, Any],
          ctx: dict[str, Any], memory: list[dict[str, Any]]) -> dict[str, Any]:
    """Every validated object gets exactly one disposition and one destination (section 21)."""
    donations: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    receipts: list[dict[str, Any]] = []

    def bump(k: str) -> None:
        counts[k] = counts.get(k, 0) + 1

    for rec in recs:
        o = rec["object"]
        t, disp = o["object_type"], o["disposition"]
        nov = novelty(o, memory)
        if nov["class"] == "EXACT_DUPLICATE":
            bump("duplicate")
            _append(root / FROZEN, {"sighting_of": nov["of"], "lab": lab, **prov,
                                    "at": _iso(_now_dt())})
            receipts.append({"title": o.get("title"), "route": "DUPLICATE", "of": nov["of"]})
            continue
        frozen = freeze(root, o, nov, {**prov, "lab": lab})
        memory.append(frozen)
        hid, tfid = frozen["hypothesis_id"], frozen["trial_family_id"]
        _append(root / ds.EVIDENCE, {"ts": _iso(_now_dt()), "lab": lab, "hypothesis_id": hid,
                                     "trial_family_id": tfid, "novelty": nov["class"],
                                     "type": t, "disposition": disp, "reasons": o["reasons"],
                                     "title": str(o.get("title") or "")[:300],
                                     "object": o, **prov})
        for dr in rec["data_requests"]:
            dr["parent_hypothesis"] = hid
            file_request(root, dr, prov)
            bump("data_request")
        if disp == "INVALID":
            bump("invalid")
            receipts.append({"hypothesis_id": hid, "route": "NEGATIVE_MEMORY",
                             "reasons": o["reasons"]})
            continue
        if t in ("DATA_REQUEST", "SOURCE_ACQUISITION_REQUEST", "VALIDATION_ATTACK") or \
                (t == "REPRESENTATION_REQUEST" and disp != "TESTABLE_NOW"):
            rid = file_request(root, o, prov)
            bump(t.lower())
            receipts.append({"hypothesis_id": hid, "route": "REQUEST_LEDGER", "request_id": rid})
            continue
        if t in ("CAPABILITY_CHALLENGER", "RESEARCH_METHOD_CHALLENGER"):
            walk = ds._propose_capability_walk(
                name=str(o.get("title")), source=str(o.get("source") or o.get("repository")
                                                     or "deepseek"),
                mechanism=str(o.get("mechanism") or o.get("economic_mechanism") or ""),
                evidence_grade=o.get("evidence_grade"), root=root)
            bump("challenger")
            receipts.append({"hypothesis_id": hid, "route": "CAPABILITY_WALK",
                             "status": walk.get("status")})
            continue
        if t == "NEGATIVE_KNOWLEDGE":
            bump("negative")
            receipts.append({"hypothesis_id": hid, "route": "NEGATIVE_MEMORY"})
            continue
        donations.append(_donation_row(o, hid, tfid, lab))
        if disp == "TESTABLE_NOW":
            bump("exact")
            if nov["class"] != "PARAMETER_NEIGHBOUR":
                bump_n = register_debt(root, o, hid, tfid, ctx["universe"])
                counts["debt_registered"] = counts.get("debt_registered", 0) + bump_n
            receipts.append({"hypothesis_id": hid, "route": "COMPILER_EXACT_RECIPE",
                             "novelty": nov["class"]})
        else:
            bump("deepening")
            receipts.append({"hypothesis_id": hid, "route": "COMPILER_DEEPENING",
                             "disposition": disp})
    path = donate(root, donations, lab)
    return {"counts": counts, "receipts": receipts, "donated_to": str(path) if path else None}


# ------------------------------------------------------------------------- feedback


def refresh_attribution(root: Path, *, now: datetime | None = None) -> dict[str, Any]:
    """Section 25. Join compiler receipts and gate verdicts back to the hypothesis that caused
    them, and credit lab / model / prompt version. Reads only; never feeds a held-out answer into
    a cold phase (the packet's blinding still strips outcomes before any prompt)."""
    t = now or _now_dt()
    memory = load_memory(root)
    by_hid = {m["hypothesis_id"]: m for m in memory}
    compiled: dict[str, list[dict[str, Any]]] = {}
    out_path = root / COMPILER_OUT
    try:
        text = out_path.read_text("utf-8") if out_path.stat().st_size < 400_000_000 else ""
    except OSError:
        text = ""
    compiler_status = "UNMEASURED: compiler output absent" if not text else "MEASURED"
    if "deepseek://" in text:
        try:
            doc = json.loads(text)
            rows = ((doc.get("hypotheses") or doc.get("candidates")) if isinstance(doc, dict)
                    else doc)
            for c in rows or []:
                url = str((c or {}).get("source_url") or "")
                if url.startswith("deepseek://"):
                    hid = url.rstrip("/").split("/")[-1]
                    if hid.startswith("dsc_"):
                        hid = url.split("/")[-2]
                    compiled.setdefault(hid, []).append(c)
        except ValueError:
            compiler_status = "UNMEASURED: compiler output unparseable"
    verdicts: dict[str, dict[str, Any]] = {}
    if compiled:
        try:
            from libs.research.hypothesis_graph import node_id_for_spec
            gid_to_hid = {}
            for hid, cands in compiled.items():
                for c in cands:
                    with_spec = {"symbol": c.get("symbol"), "family": c.get("family"),
                                 "params": c.get("params") or {}}
                    gid_to_hid[node_id_for_spec(with_spec)] = hid
            from collections import deque
            with (root / GATE_LEDGER).open(encoding="utf-8") as fh:
                for line in deque(fh, maxlen=GATE_TAIL):
                    try:
                        r = json.loads(line)
                    except ValueError:
                        continue
                    vhid = gid_to_hid.get(str(r.get("graph_id") or ""))
                    if vhid:
                        v = verdicts.setdefault(vhid, {"judged": 0, "passed": 0, "gates": {}})
                        v["judged"] += 1
                        v["passed"] += int(bool(r.get("passed")))
                        g = str(r.get("terminal_gate") or "UNKNOWN")
                        v["gates"][g] = v["gates"].get(g, 0) + 1
        except (OSError, ImportError):
            pass
    calls = _load(root / ATTRIBUTION, {}).get("calls") or []
    by: dict[str, dict[str, dict[str, float]]] = {"by_lab": {}, "by_model": {}, "by_family": {},
                                                  "by_prompt": {}}

    def acc(kind: str, key: str, field: str, n: float = 1.0) -> None:
        row = by[kind].setdefault(key or "?", {})
        row[field] = row.get(field, 0) + n

    for c in calls:
        for kind, key in (("by_lab", c.get("lab")), ("by_model", c.get("model")),
                          ("by_family", model_family(str(c.get("model") or ""))),
                          ("by_prompt", c.get("prompt_version"))):
            acc(kind, str(key), "calls")
            acc(kind, str(key), "valid_json", 1.0 if c.get("schema") == "OK" else 0.0)
            for f in ("exact", "duplicate", "invalid", "data_request", "deepening"):
                acc(kind, str(key), f, float((c.get("counts") or {}).get(f, 0)))
            acc(kind, str(key), "requests", float(sum(
                (c.get("counts") or {}).get(f, 0) for f in ("data_request", "validation_attack",
                                                            "representation_request"))))
    for hid, m in by_hid.items():
        for kind, key in (("by_lab", m.get("lab")), ("by_model", m.get("model")),
                          ("by_family", model_family(str(m.get("model") or ""))),
                          ("by_prompt", m.get("prompt_version"))):
            if hid in compiled:
                acc(kind, str(key), "compiled")
            vd = verdicts.get(hid)
            if vd:
                acc(kind, str(key), "judged", vd["judged"])
                acc(kind, str(key), "passed", vd["passed"])
    doc = {"updated_utc": _iso(t), "calls": calls[-5000:], **by,
           "compiler": {"status": compiler_status, "hypotheses_compiled": len(compiled),
                        "candidates": sum(len(v) for v in compiled.values())},
           "gauntlet": {"status": ("MEASURED" if (root / GATE_LEDGER).exists()
                                   else "UNMEASURED: gate ledger absent"),
                        "hypotheses_judged": len(verdicts),
                        "hypotheses_passed": sum(1 for v in verdicts.values() if v["passed"]),
                        "verdicts": verdicts}}
    _save(root / ATTRIBUTION, doc)
    return doc


def record_call(root: Path, row: dict[str, Any]) -> None:
    doc = _load(root / ATTRIBUTION, {})
    if not isinstance(doc, dict):
        doc = {}
    doc.setdefault("calls", []).append(row)
    doc["calls"] = doc["calls"][-5000:]
    _save(root / ATTRIBUTION, doc)


