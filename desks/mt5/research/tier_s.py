"""TIER S -- the autonomous research institution's hourly organ.

The principal's Tier S blueprint (30 layers) and its final hardening layer (16 more) were closed on
2026-09-29 with one rule: no subsystem ships because it sounds sophisticated; each must measurably
raise independent-alpha discovery, falsification power, information per compute, calibration or
execution capture, or cut false discoveries or operational risk. `docs/research/tier_s_program.json`
is the ledger of the 46 layers, each with a MEASURABLE CONTRACT; this organ runs every kernel in
`libs/tiers/` against the desk's own artifacts, writes one report per kernel under
`reports/tier_s/`, evaluates every layer's contract on its metric's history, and ends with the
self-model: the desk's largest deficiency, ranked, and the architecture challengers it is running.

WHAT IT CHANGES (research side only -- nothing here sizes, admits, certifies or places):

  * data/intelligence/tier_s/*.json   hypothesis rows for the compiler: MAP-Elites empty niches,
                                      topology-steered orthogonal directions, broken structural
                                      relationships and cross-science labs. ADDS candidates; never
                                      removes, throttles or re-orders a miner.
  * data/tier_s/truth_journal.jsonl   the content-addressed lineage (append-only, hash-chained)
  * data/tier_s/*.json                organ state (Red Queen populations, genomes, ledgers)
  * data/tier_s/PROMOTION_FREEZE.json the immune system's verdict. PUBLISHED, NOT CONSUMED: the
                                      promoter reading it is a money-path change that waits for the
                                      principal's word.

Each kernel runs isolated (one failure never stops the rest) and records its seconds, so the
researcher market can price this organ like any other.

    python desks/mt5/research/tier_s.py [--only immune,formal] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import traceback
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import contextlib

from libs.tiers import (  # noqa: E402
    bitemporal,
    chaos,
    contracts,
    cross_science,
    epistemic,
    evolution,
    failure_memory,
    firewall,
    formal,
    frontier,
    meta_benchmark,
    online_fdr,
    opportunity_exchange,
    prediction_accounting,
    red_queen,
    replay,
    researcher_market,
    review_panel,
    self_model,
    test_invention,
    theory,
    topology,
    truth_kernel,
    twin,
    world_edges,
)

PRODUCTION_ARGS: list[str] = []

REPORTS = DESK / "reports"
OUT_DIR = REPORTS / "tier_s"
SUMMARY = REPORTS / "TIER_S.json"
STATE = DESK / "data" / "tier_s"
INTEL = DESK / "data" / "intelligence" / "tier_s"
LEDGER = ROOT / "docs" / "research" / "tier_s_program.json"
CONSTITUTION = ROOT / "docs" / "research" / "tier_s_constitution.json"
RATIFICATIONS = ROOT / "docs" / "research" / "tier_s_ratifications.jsonl"

SURVIVORS = (REPORTS / "UNIVERSAL_SURVIVORS.json", DESK / "data" / "UNIVERSAL_SURVIVORS.canon.json")
REGISTRY = DESK / "data" / "sleeve_registry.json"
GATE_LEDGER = DESK / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"
LIVE_LEDGER = DESK / "data" / "live_ledger.jsonl"
ORDER_INTENTS = DESK / "data" / "order_intents.jsonl"
DECISIONS = DESK / "data" / "decision_ledger.jsonl"
EVENTS = DESK / "data" / "events.jsonl"
COMPUTE = DESK / "data" / "compute_ledger.jsonl"
HGRAPH = DESK / "data" / "hypothesis_graph.jsonl"
UNIVERSE = DESK / "data" / "universe"
SHADOW_STATES = tuple((REPORTS / "shadow").glob("*shadow_state.json")) if (
    REPORTS / "shadow").exists() else ()
PF_ALLOCATION = (REPORTS / "pf_allocation.json", DESK / "data" / "pf_allocation.json")
FORECAST_LOG = DESK / "data" / "pf_forecast_log.jsonl"

#: ledgers that must only ever grow (the evidence seal)
PROTECTED = (GATE_LEDGER, LIVE_LEDGER, ORDER_INTENTS, DECISIONS, FORECAST_LOG,
             DESK / "data" / "hypotheses" / "trial_ledger.jsonl",
             DESK / "data" / "preregistrations.jsonl", DESK / "data" / "decision_dataset.jsonl")

MAX_EMIT_PER_KIND = 150
NOW = datetime.now(UTC)


# ------------------------------------------------------------------------------------------------
# small io helpers
# ------------------------------------------------------------------------------------------------

def _read(p: Path) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _first(paths: Iterable[Path]) -> Any:
    for p in paths:
        d = _read(p)
        if d is not None:
            return d
    return None


def _write(p: Path, doc: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str, sort_keys=False), encoding="utf-8")
    os.replace(tmp, p)


def _jsonl(p: Path, limit: int = 400_000) -> list[dict[str, Any]]:
    return replay.read_jsonl(p, limit)


def _state(name: str) -> dict[str, Any]:
    d = _read(STATE / f"{name}.json")
    return d if isinstance(d, dict) else {}


def _save_state(name: str, doc: Mapping[str, Any]) -> None:
    _write(STATE / f"{name}.json", dict(doc))


def survivors() -> dict[str, Any]:
    d = _first(SURVIVORS)
    if isinstance(d, dict):
        s = d.get("survivors", d)
        return s if isinstance(s, dict) else {}
    return {}


def registry() -> dict[str, Any]:
    d = _read(REGISTRY)
    s = (d or {}).get("sleeves") if isinstance(d, dict) else None
    return s if isinstance(s, dict) else {}


def shadow_rows() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for p in SHADOW_STATES:
        d = _read(p)
        if isinstance(d, dict):
            for k, v in d.items():
                if isinstance(v, dict) and "n" in v:
                    out.setdefault(str(k), v)
    return out


def _spec(row: Mapping[str, Any]) -> dict[str, Any]:
    s = row.get("shadow_spec") or row.get("identity") or {}
    return s if isinstance(s, dict) else {}


def _asset_class(sym: str) -> str:
    try:
        import universe_policy
        return str(universe_policy.asset_class_of(sym))
    except Exception:
        return "UNCLASSIFIED"


def _may_hypothesise(sym: str) -> bool:
    try:
        import universe_policy
        return bool(universe_policy.may_hypothesise(sym))
    except Exception:
        return False


def _mechanism(family: str) -> str:
    try:
        import axis_registry
        return str(axis_registry.classify_family(family)[0])
    except Exception:
        return family or "UNKNOWN"


def _family_vocab() -> list[str]:
    try:
        import miner_candidate_compiler as mcc
        vocab = getattr(mcc, "_FAMILY_VOCAB", {})
        return sorted(k for k in vocab if mcc._registered_cached(k))
    except Exception:
        return []


def _emit(kind: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Write hypothesis rows where the compiler reads (data/intelligence/**)."""
    rows = [r for r in rows if r.get("symbols")][:MAX_EMIT_PER_KIND]
    if not rows:
        return {"kind": kind, "emitted": 0}
    stamp = NOW.strftime("%Y%m%dT%H")
    for r in rows:
        r.setdefault("found_at", NOW.isoformat())
        r.setdefault("source", f"tier_s:{kind}")
        r.setdefault("seat", "tier_s")
    _write(INTEL / f"{kind}_{stamp}.json", {"kind": kind, "generated_utc": NOW.isoformat(),
                                             "rows": rows})
    return {"kind": kind, "emitted": len(rows)}


def _returns_panel(max_symbols: int = 28, bars: int = 3000) -> tuple[dict[str, np.ndarray],
                                                                        dict[str, np.ndarray],
                                                                        dict[str, np.ndarray]]:
    """H1 log returns (plus closes and tick volumes) for hypothesis-eligible symbols."""
    rets: dict[str, np.ndarray] = {}
    closes: dict[str, np.ndarray] = {}
    vols: dict[str, np.ndarray] = {}
    if not UNIVERSE.exists():
        return rets, closes, vols
    try:
        import pandas as pd
    except ImportError:
        return rets, closes, vols
    files = sorted(UNIVERSE.glob("*_H1.parquet"), key=lambda p: -p.stat().st_size)
    for p in files:
        sym = p.name[: -len("_H1.parquet")]
        if not _may_hypothesise(sym):
            continue
        try:
            df = pd.read_parquet(p)
        except Exception:
            continue
        if "close" not in df or len(df) < 500:
            continue
        c = df["close"].astype(float).to_numpy()[-bars:]
        c = c[np.isfinite(c) & (c > 0)]
        if len(c) < 500:
            continue
        closes[sym] = c
        rets[sym] = np.diff(np.log(c))
        for vk in ("tick_volume", "volume", "real_volume"):
            if vk in df:
                vols[sym] = df[vk].astype(float).to_numpy()[-len(c):]
                break
        if len(rets) >= max_symbols:
            break
    if rets:
        n = min(len(v) for v in rets.values())
        rets = {k: v[-n:] for k, v in rets.items()}
    return rets, closes, vols


# ------------------------------------------------------------------------------------------------
# organs
# ------------------------------------------------------------------------------------------------

def organ_truth_kernel() -> dict[str, Any]:
    j = truth_kernel.Journal(STATE / "truth_journal.jsonl").load()
    surv = survivors()
    cert_by_sleeve: dict[str, str] = {}
    added = Counter()
    before = len(j.nodes())
    for key, row in surv.items():
        if not isinstance(row, dict):
            continue
        spec = _spec(row)
        sym, fam = str(spec.get("symbol") or row.get("sym") or ""), str(spec.get("family") or "")
        hyp = j.put("hypothesis", {"cell": row.get("cell") or key, "symbol": sym, "family": fam,
                                   "selector": spec.get("selector")},
                    at=str(row.get("gated_at") or NOW.isoformat()))
        exp = j.put("experiment", {"gates": row.get("gates") or {}, "days": row.get("days"),
                                   "hunt": row.get("hunt")}, [hyp.id],
                    at=str(row.get("gated_at") or NOW.isoformat()))
        cert = j.put("certificate", {"key": key, "gated_at": row.get("gated_at")}, [exp.id],
                     at=str(row.get("gated_at") or NOW.isoformat()))
        for k in (f"{sym}.{spec.get('selector')}", f"{sym}.{fam}.{spec.get('selector')}",
                  str(key)):
            cert_by_sleeve[k] = cert.id
    alloc_rows = [r for r in _jsonl(FORECAST_LOG, 50_000) if isinstance(r.get("book"), dict)]
    alloc_ids: list[tuple[str, str]] = []
    for r in alloc_rows[-500:]:
        book = r.get("book") or {}
        parents = sorted({cert_by_sleeve[k] for k in book if k in cert_by_sleeve})
        a = j.put("allocation", {"t": r.get("t"), "book": book, "total_heat": r.get("total_heat"),
                                 "certified": r.get("certified")}, parents,
                  at=str(r.get("t") or NOW.isoformat()))
        alloc_ids.append((str(r.get("t") or ""), a.id))
    alloc_ids.sort()

    def alloc_before(t: str) -> str | None:
        prev = None
        for at, aid in alloc_ids:
            if at <= t:
                prev = aid
            else:
                break
        return prev

    order_by_ticket: dict[str, str] = {}
    for r in _jsonl(ORDER_INTENTS, 100_000):
        t = str(r.get("time") or "")
        parents = [p for p in (alloc_before(t), cert_by_sleeve.get(str(r.get("sleeve"))))
                   if p]
        o = j.put("order", {k: r.get(k) for k in ("sleeve", "symbol", "side", "lot", "intended",
                                                  "sl", "tp", "ticket", "retcode", "time")},
                  parents, at=t or NOW.isoformat())
        if r.get("ticket"):
            order_by_ticket[str(r.get("ticket"))] = o.id
    for r in _jsonl(LIVE_LEDGER, 100_000):
        t = str(r.get("time") or "")
        op = order_by_ticket.get(str(r.get("order")))
        parents = [op] if op else [p for p in (alloc_before(t),
                                               cert_by_sleeve.get(str(r.get("sleeve")))) if p]
        j.put("fill", {k: r.get(k) for k in ("sleeve", "symbol", "side", "volume", "fill_price",
                                             "deal", "order", "pl_quote", "time")},
              parents, at=t or NOW.isoformat())
    for n in j.nodes():
        added[n.kind] += 1
    ver = j.verify()
    cov = j.coverage()
    # the constitution and the evidence seal
    sealed = truth_kernel.constitution_doc()
    live = _read(CONSTITUTION) or sealed
    ratifs = _jsonl(RATIFICATIONS)
    const = truth_kernel.constitution_status(sealed, live, ratifs)
    prev_seal = _state("evidence_seal")
    seal = truth_kernel.seal_ledgers(list(PROTECTED), prev_seal, DESK)
    hist = list(prev_seal.get("violations_history") or [])
    if seal["violations"]:
        hist.append({"at": NOW.isoformat(), "violations": seal["violations"]})
    _save_state("evidence_seal", {**seal, "violations_history": hist[-200:]})
    return {"verify": ver, "coverage": cov, "nodes_by_kind": dict(added),
            "new_nodes": len(j.nodes()) - before, "constitution": const,
            "evidence_seal": {"n_ledgers": seal["n"], "violations": seal["violations"]},
            "metric": {"fill_reconstructible_share": cov.get("share"),
                       "journal_ok": 1.0 if ver.get("ok") else 0.0,
                       "rewrites": sum(1 for v in seal["violations"] if v["kind"] == "REWRITTEN"),
                       "constitution_violation": 1.0 if const["status"] == "VIOLATION" else 0.0}}


def organ_firewall() -> dict[str, Any]:
    audit = firewall.audit(ROOT)
    st = _state("firewall")
    base = st.get("baseline")
    rat = firewall.ratchet(audit, base)
    if base is None or len(audit["violations"]) < len((base or {}).get("violations") or []):
        st["baseline"] = {"violations": audit["violations"], "at": NOW.isoformat()}
    _save_state("firewall", st)
    return {"audit": audit, "ratchet": rat,
            "metric": {"violations": audit["n_violations"], "breach": 1.0 if rat["breach"]
                       else 0.0}}


def _incumbent_validator() -> meta_benchmark.ValidatorConfig:
    ad = _state("adopted")
    g = ad.get("validator")
    if isinstance(g, dict):
        try:
            g = dict(g)
            g["extra"] = tuple(tuple(x) for x in g.get("extra") or [])
            return meta_benchmark.ValidatorConfig(**g)
        except TypeError:
            pass
    return meta_benchmark.ValidatorConfig()


def organ_immune() -> dict[str, Any]:
    suite = meta_benchmark.Suite(per_kind=12)
    cfg = _incumbent_validator()
    seal = suite.seal()
    res = meta_benchmark.score(meta_benchmark.reference_validator(cfg), suite)
    st = _state("immune")
    hist = list(st.get("history") or [])
    const = _read(CONSTITUTION) or truth_kernel.constitution_doc()
    floor = float(((const.get("rules") or {}).get("immune.min_trap_rejection") or {})
                  .get("value", 0.9))
    verdict = meta_benchmark.immune_verdict(res, hist, floor=floor, seal=seal)
    hist.append({"at": NOW.isoformat(), "seal": seal, "immune_score": res["immune_score"],
                 "power": res["power"]})
    _save_state("immune", {"history": hist[-500:]})
    _write(STATE / "PROMOTION_FREEZE.json", {
        "verdict": verdict["verdict"], "why": verdict.get("why"), "at": NOW.isoformat(),
        "consumer": "NONE YET -- the promoter reading this is a money-path change awaiting the "
                    "principal's word", "immune_score": res["immune_score"], "seal": seal})
    return {"score": res, "seal": seal, "verdict": verdict, "floor": floor,
            "validator": cfg.genome(),
            "metric": {"immune_score": res["immune_score"], "power": res["power"],
                       "balanced": res["balanced"]}}


def organ_test_invention() -> dict[str, Any]:
    inc = _incumbent_validator()
    out = test_invention.invent(inc, meta_benchmark.Suite(per_kind=6, base_seed=31337),
                                meta_benchmark.Suite(per_kind=6, base_seed=424242))
    st = _state("candidate_gates")
    reg = {json.dumps(g["check"]): g for g in st.get("gates") or []}
    for g in out["candidate_gates"]:
        k = json.dumps(g["check"])
        reg.setdefault(k, {**g, "first_seen": NOW.isoformat(), "confirmations": 0})
        reg[k]["confirmations"] = int(reg[k].get("confirmations", 0)) + 1
        reg[k]["last_seen"] = NOW.isoformat()
    _save_state("candidate_gates", {"gates": list(reg.values())})
    return {**out, "registry_size": len(reg),
            "metric": {"candidate_gates": len(out["candidate_gates"]),
                       "registry": len(reg)}}


def organ_red_queen() -> dict[str, Any]:
    st = _state("red_queen")
    attackers = red_queen.from_state(st)
    sealed = list(meta_benchmark.Suite(per_kind=4, base_seed=5150, n=1200).cases())
    gen = int(st.get("generation", 0)) + 1
    res = red_queen.generation(attackers, _incumbent_validator(), sealed, seed=gen)
    hist = list(st.get("success_history") or [])
    hist.append({"gen": gen, "at": NOW.isoformat(), "attack_success": res["attack_success"]})
    _save_state("red_queen", {"generation": gen, "attackers": res["next_attackers"],
                              "success_history": hist[-500:],
                              "challenger": res["challenger"]})
    if res["challenger"]:
        _register_challenger("validator", f"red_queen_gen{gen}", res["challenger"],
                             res["best_defender"])
    return {"generation": gen, **{k: v for k, v in res.items() if k != "next_attackers"},
            "metric": {"attack_success": res["attack_success"],
                       "defender_balanced": res["best_defender"]["balanced"]}}


def organ_online_fdr() -> dict[str, Any]:
    tests: list[online_fdr.Test] = []
    surv = survivors()
    tests.extend(online_fdr.tests_from_survivors(surv))
    seen = {t.test_id for t in tests}
    n_gate = 0
    for r in _jsonl(GATE_LEDGER):
        cell = str(r.get("cell") or "")
        if not cell or cell in seen or r.get("passed"):
            continue
        n_gate += 1
        tests.append(online_fdr.Test(test_id=cell, at=str(r.get("at") or ""), p=1.0,
                                     family=str(r.get("family") or "")))
    res = online_fdr.replay(tests)
    rows = res.pop("rows")
    over = [r for r in rows if r["over_budget"]]
    _write(OUT_DIR / "ONLINE_FDR_ROWS.json", {"generated_utc": NOW.isoformat(),
                                              "over_budget": over[:500],
                                              "certified": [r for r in rows if r["certified"]]})
    return {**res, "failed_tests_charged": n_gate,
            "note": "failed trials enter at p=1: they spend lifetime budget without earning it",
            "metric": {"over_budget_share": res["over_budget_share"],
                       "lord_discoveries": res["lord_discoveries"]}}


def _sleeve_descriptors() -> tuple[list[str], list[dict[str, Any]]]:
    names, descs = [], []
    for k, v in registry().items():
        if not isinstance(v, dict) or v.get("status") not in ("LIVE", "STANDBY", "ACTIVE"):
            continue
        idn = v.get("identity") or {}
        fam = str(idn.get("family") or "")
        sym = str(idn.get("symbol") or "")
        names.append(str(k))
        descs.append({"family": fam, "mechanism": _mechanism(fam), "symbol": sym,
                      "asset_class": _asset_class(sym), "selector": idn.get("selector"),
                      "direction": idn.get("direction"), "timeframe": idn.get("timeframe"),
                      "code": idn.get("code_hash")})
    return names, descs


def organ_topology() -> dict[str, Any]:
    names, descs = _sleeve_descriptors()
    # live daily R per sleeve where the ledger has fills
    daily: dict[str, dict[str, float]] = defaultdict(dict)
    for r in _jsonl(LIVE_LEDGER):
        s, t = str(r.get("sleeve") or ""), str(r.get("time") or "")[:10]
        if s and t:
            daily[s][t] = daily[s].get(t, 0.0) + float(r.get("pl_quote") or 0.0)
    pnl = None
    pnl_names = [n for n in names if n in daily]
    if len(pnl_names) >= 2:
        days = sorted({d for n in pnl_names for d in daily[n]})
        pnl = np.array([[daily[n].get(d, 0.0) for n in pnl_names] for d in days])
    rank = topology.rank_report(None, names, descs)
    if pnl is not None and pnl.shape[0] >= 10:
        rank["live_pnl"] = topology.rank_report(pnl, pnl_names, None)
    steer = topology.steering(descs, rank.get("uniqueness"), names,
                              ("mechanism", "asset_class", "selector", "timeframe"))
    # ancestry novelty over the hypothesis graph (parent -> child)
    nodes: dict[str, dict[str, Any]] = {}
    for r in _jsonl(HGRAPH, 60_000):
        nid = str(r.get("id") or "")
        if not nid:
            continue
        par = r.get("parent")
        nodes[nid] = {"parents": [str(par)] if par and str(par) in nodes else [],
                      "descriptors": {"family": r.get("family"), "symbol": r.get("symbol"),
                                      "source": str(r.get("source") or "").split(":")[0]}}
    nov = topology.novelty(nodes) if nodes else {}
    eff = topology.effective_discoveries(nov)
    st = _state("topology")
    hist = list(st.get("rank_history") or [])
    hist.append({"at": NOW.isoformat(), "combined": rank.get("combined"), "n": len(names)})
    _save_state("topology", {"rank_history": hist[-2000:]})
    # orthogonal directions -> hypotheses: the least-occupied mechanisms on new symbols
    emitted = _emit_orthogonal(steer, descs)
    return {"rank": rank, "steering": steer, "ancestry": eff, "emitted": emitted,
            "metric": {"effective_rank": rank.get("combined"), "n_sleeves": len(names),
                       "effective_discoveries": eff.get("effective")}}


def _emit_orthogonal(steer: Mapping[str, Mapping[str, float]],
                     descs: list[dict[str, Any]]) -> dict[str, Any]:
    vocab = _family_vocab()
    if not vocab:
        return {"kind": "orthogonal", "emitted": 0, "why": "family vocabulary unavailable"}
    held = {(d["family"], d["symbol"]) for d in descs}
    mech_w = steer.get("mechanism") or {}
    fam_w = {f: mech_w.get(_mechanism(f), 1.0) for f in vocab}
    syms = [p.name[: -len("_H1.parquet")] for p in UNIVERSE.glob("*_H1.parquet")] if \
        UNIVERSE.exists() else []
    syms = [s for s in syms if _may_hypothesise(s)]
    cls_w = steer.get("asset_class") or {}
    rows = []
    for f in sorted(vocab, key=lambda x: -fam_w[x]):
        for s in sorted(syms, key=lambda x: -cls_w.get(_asset_class(x), 1.0)):
            if (f, s) in held:
                continue
            rows.append({"kind": "hypothesis", "family": f, "symbols": [s],
                         "text": f"tier_s orthogonal direction: {f} on {s} -- mechanism weight "
                                 f"{fam_w[f]:.3f}, asset-class weight "
                                 f"{cls_w.get(_asset_class(s), 1.0):.3f} vs the effective basis",
                         "steering": {"mechanism": fam_w[f],
                                      "asset_class": cls_w.get(_asset_class(s), 1.0)}})
            if len(rows) >= MAX_EMIT_PER_KIND:
                break
        if len(rows) >= MAX_EMIT_PER_KIND:
            break
    return _emit("orthogonal", rows)


def organ_qd() -> dict[str, Any]:
    arch = evolution.Archive(("mechanism", "asset_class", "selector", "timeframe", "direction"))
    shadow = shadow_rows()
    for key, row in survivors().items():
        if not isinstance(row, dict):
            continue
        spec = _spec(row)
        sym, fam = str(spec.get("symbol") or row.get("sym") or ""), str(spec.get("family") or "")
        q = float(((row.get("gates") or {}).get("expected_value") or {}).get("ev") or 0.0)
        fw = shadow.get(f"{sym}.{spec.get('selector')}") or {}
        if fw.get("exp_r") is not None:
            q = 0.5 * q + 0.5 * float(fw["exp_r"])
        arch.add(str(key), {"mechanism": _mechanism(fam), "asset_class": _asset_class(sym),
                            "selector": spec.get("selector") or "?", "timeframe":
                            spec.get("timeframe") or "H1", "direction":
                            spec.get("direction") or "?", "family": fam, "symbol": sym}, q)
    cov = arch.coverage()
    empty = arch.marginal_empty([("mechanism", "asset_class"), ("mechanism", "selector")],
                                top=400)
    # empty (mechanism, asset class) niches -> registered families of that mechanism on symbols
    # of that class that are eligible for hypotheses
    vocab = _family_vocab()
    by_mech: dict[str, list[str]] = defaultdict(list)
    for f in vocab:
        by_mech[_mechanism(f)].append(f)
    syms = [p.name[: -len("_H1.parquet")] for p in UNIVERSE.glob("*_H1.parquet")] if \
        UNIVERSE.exists() else []
    by_cls: dict[str, list[str]] = defaultdict(list)
    for s in syms:
        if _may_hypothesise(s):
            by_cls[_asset_class(s)].append(s)
    rows = []
    for e in empty:
        m, c = e.get("mechanism"), e.get("asset_class")
        if not m or not c:
            continue
        for f in by_mech.get(str(m), [])[:2]:
            for s in by_cls.get(str(c), [])[:3]:
                rows.append({"kind": "hypothesis", "family": f, "symbols": [s],
                             "text": f"tier_s MAP-Elites: niche ({m}, {c}) holds no elite; "
                                     f"{f} on {s} is the probe", "niche": e})
    emitted = _emit("qd_niches", rows)
    return {"coverage": cov, "empty_projections": empty[:40], "weak": arch.weak(10),
            "emitted": emitted,
            "metric": {"niche_share": cov.get("share"), "qd_score": cov.get("qd_score"),
                       "filled": cov.get("filled")}}


def organ_genomes() -> dict[str, Any]:
    """Researcher genomes: each emits hypotheses; fitness is what the gauntlet made of them."""
    st = _state("genomes")
    rng = np.random.default_rng(int(st.get("generation", 0)) + 17)
    pop: list[dict[str, Any]] = list(st.get("population") or [])
    emitted_cells: dict[str, list[str]] = dict(st.get("emitted") or {})
    verdicts: dict[str, bool] = {}
    for r in _jsonl(GATE_LEDGER):
        c = str(r.get("cell") or "")
        if c:
            verdicts[c] = bool(r.get("passed")) or verdicts.get(c, False)
    scored: list[tuple[dict[str, Any], float]] = []
    for g in pop:
        gid = evolution.genome_id(g)
        cells = emitted_cells.get(gid, [])
        judged = [c for c in cells if c in verdicts]
        passed = sum(1 for c in judged if verdicts[c])
        stats = {"validated_independent": passed, "compute_s": max(1.0, 30.0 * len(judged)),
                 "complexity": float(g.get("complexity_cap", 4.0)),
                 "false_discoveries": 0.0, "duplicates": 0.0}
        scored.append((g, evolution.fitness(stats) if judged else 0.0))
    nxt = evolution.step(scored, rng, size=12)
    vocab = _family_vocab()
    op_family = {"momentum": ["momentum_volgate", "trend_ma_cross", "asia_momentum",
                              "london_close_momentum"],
                 "reversion": ["mean_reversion_rsi", "mean_reversion_bollinger",
                               "range_reversion"],
                 "carry": ["overnight_drift", "overnight_gap_decay"],
                 "seasonal": ["dow_effect", "turn_of_month", "calendar_month", "monday_gap"],
                 "breakout": ["session_range_breakout", "level_breakout", "failed_breakout",
                              "volatility_squeeze"],
                 "vol_regime": ["volatility_squeeze", "momentum_volgate"],
                 "lead_lag": ["london_close_momentum"], "mixed": vocab}
    syms = sorted(p.name[: -len("_H1.parquet")] for p in UNIVERSE.glob("*_H1.parquet")) if \
        UNIVERSE.exists() else []
    syms = [s for s in syms if _may_hypothesise(s)]
    rows = []
    for g in nxt:
        gid = evolution.genome_id(g)
        fams = [f for f in op_family.get(str(g.get("operator_set")), []) if f in vocab]
        if not fams or not syms:
            continue
        k = max(1, round(float(g.get("exploration", 0.3)) * 10))
        picks = rng.choice(len(syms), size=min(k, len(syms)), replace=False)
        for i in picks:
            f = fams[int(rng.integers(len(fams)))]
            s = syms[int(i)]
            rows.append({"kind": "hypothesis", "family": f, "symbols": [s], "genome": gid,
                         "text": f"tier_s researcher genome {gid} ({g.get('operator_set')}, "
                                 f"{g.get('data_policy')}, {g.get('horizon')}) proposes {f} "
                                 f"on {s}"})
            emitted_cells.setdefault(gid, []).append(f"{s}.{f}")
    emitted = _emit("genomes", rows)
    _save_state("genomes", {"generation": int(st.get("generation", 0)) + 1,
                            "population": nxt,
                            "emitted": {k: v[-400:] for k, v in emitted_cells.items()}})
    best = max((f for _g, f in scored), default=0.0)
    return {"generation": int(st.get("generation", 0)) + 1, "population": len(nxt),
            "diversity": evolution.diversity(nxt), "best_fitness": best,
            "emitted": emitted,
            "note": "fitness = gauntlet survivors among the genome's own emitted cells per "
                    "compute; cells join on SYMBOL.family prefix",
            "metric": {"best_fitness": best, "diversity": evolution.diversity(nxt)}}


def _expr_str(expr: Any) -> str:
    try:
        from libs.research.alpha_grammar import to_str
        return to_str(expr) if isinstance(expr, (list, tuple)) else str(expr or "")
    except Exception:
        return str(expr or "")


def _cell_of(sym: Any, family: Any, params: Any) -> str:
    try:
        from research.frontier_identity import cell_id
        return str(cell_id({"sym": sym, "family": family, "params": dict(params or {})}))
    except Exception:
        return ""


def _gate_passed() -> dict[str, bool]:
    """cell -> passed (latest verdict wins), from the gauntlet's own ledger."""
    out: dict[str, bool] = {}
    for r in _jsonl(GATE_LEDGER):
        c = str(r.get("cell") or "")
        if c:
            out[c] = bool(r.get("passed"))
    return out


def _formula_programs() -> tuple[list[tuple[str, bool]], list[str], int]:
    """Every formula the generators proposed, labelled by what the gauntlet made of it.

    alpha_evolution writes `discoveries` with the formula as a prefix list in `params.expr`
    (daily files plus gzipped jsonl rollups). A program counts toward operator yield only once
    the gauntlet has judged its exact cell; survivors also come from the canon rows that carry
    an expression. Returns (judged programs, surviving expressions, proposed count)."""
    import gzip
    root = DESK / "data" / "intelligence" / "alpha_evolution"
    judged = _gate_passed()
    rows: list[dict[str, Any]] = []
    if root.exists():
        for p in sorted(root.glob("*.json"))[-400:]:
            d = _read(p)
            if isinstance(d, dict):
                rows.extend(r for r in d.get("discoveries") or [] if isinstance(r, dict))
        for p in sorted(root.glob("*.jsonl.gz"))[-60:]:
            try:
                with gzip.open(p, "rt", encoding="utf-8") as fh:
                    for line in fh:
                        try:
                            r = json.loads(line)
                        except ValueError:
                            continue
                        if isinstance(r, dict):
                            rows.extend(x for x in (r.get("discoveries") or [r])
                                        if isinstance(x, dict))
            except (OSError, EOFError):
                continue
    progs: list[tuple[str, bool]] = []
    surv: list[str] = []
    seen: set[str] = set()
    for r in rows:
        params = r.get("params") or {}
        expr = params.get("expr") if isinstance(params, dict) else None
        if expr is None:
            continue
        e = _expr_str(expr)
        cell = _cell_of(r.get("symbol") or r.get("sym"), r.get("family") or "formula", params)
        if not e or cell in seen:
            continue
        seen.add(cell)
        if cell in judged:
            progs.append((e, judged[cell]))
            if judged[cell]:
                surv.append(e)
    for row in survivors().values():
        if not isinstance(row, dict):
            continue
        for src in (row.get("params"), (row.get("shadow_spec") or {}).get("params")):
            if isinstance(src, dict) and src.get("expr") is not None:
                surv.append(_expr_str(src["expr"]))
    ef = _read(REPORTS / "EXPRESSION_FACTORY.json") or {}
    for r in ef.get("survivors") or [] if isinstance(ef, dict) else []:
        if isinstance(r, dict):
            e = r.get("expr") or r.get("expression") or (r.get("params") or {}).get("expr")
            if e is not None:
                surv.append(_expr_str(e))
    return progs, surv, len(seen)


def organ_grammar() -> dict[str, Any]:
    """Operator yield and learned abstractions (layers 22 and 44) from judged formulas.

    The primitives are written to data/tier_s/grammar.json, which expression_factory reads as
    extra terminals: the learned vocabulary is used, not only reported."""
    progs, survivors_expr, proposed = _formula_programs()
    oy = evolution.operator_yield(progs) if progs else {"operators": {}, "retired": []}
    ab = evolution.abstractions(survivors_expr) if survivors_expr else {"primitives": [],
                                                                        "n_primitives": 0}
    _save_state("grammar", {"operator_weights": {k: v["weight"] for k, v in
                                                 (oy.get("operators") or {}).items()},
                            "retired": oy.get("retired") or [],
                            "primitives": ab.get("primitives"),
                            "generated_utc": NOW.isoformat()})
    return {"n_proposed": proposed, "n_programs": len(progs),
            "n_survivor_exprs": len(survivors_expr), "operator_yield": oy, "abstractions": ab,
            "metric": {"n_primitives": ab.get("n_primitives"),
                       "judged_programs": len(progs),
                       "retired_operators": len(oy.get("retired") or [])}}


def organ_theory() -> dict[str, Any]:
    g = theory.TheoryGraph()
    shadow = shadow_rows()
    try:
        import mechanism_ontology as mo  # type: ignore[import-not-found]
    except Exception:
        mo = None
    mech_cache: dict[str, theory.Mechanism] = {}

    def mech_for(fam: str) -> theory.Mechanism:
        if fam in mech_cache:
            return mech_cache[fam]
        raw: dict[str, Any] = {"mechanism": _mechanism(fam), "family": fam}
        if mo is not None:
            for name in ("describe", "ontology_for", "lookup"):
                fn = getattr(mo, name, None)
                if callable(fn):
                    try:
                        got = fn(fam)
                        if isinstance(got, dict):
                            raw.update(got)
                        break
                    except Exception:
                        continue
        m = theory.compile_mechanism(raw, family=fam)
        mech_cache[fam] = m
        return m

    n_back = 0
    for r in _jsonl(GATE_LEDGER):
        fam = str(r.get("family") or "")
        if not fam:
            continue
        g.theory(mech_for(fam)).add(experiment=str(r.get("cell")), supports=bool(r.get("passed")),
                                    source="backtest", context=str(r.get("sym") or ""))
        n_back += 1
    for key, row in survivors().items():
        if not isinstance(row, dict):
            continue
        spec = _spec(row)
        fam = str(spec.get("family") or "")
        if not fam:
            continue
        fw = shadow.get(f"{spec.get('symbol')}.{spec.get('selector')}") or {}
        if fw.get("n") and int(fw["n"]) >= 5 and fw.get("exp_r") is not None:
            g.theory(mech_for(fam)).add(experiment=f"forward:{key}",
                                        supports=float(fw["exp_r"]) > 0, source="forward",
                                        context=str(spec.get("symbol")))
    live_by: dict[str, float] = defaultdict(float)
    for r in _jsonl(LIVE_LEDGER):
        live_by[str(r.get("sleeve") or "")] += float(r.get("pl_quote") or 0.0)
    for k, v in registry().items():
        fam = str(((v or {}).get("identity") or {}).get("family") or "")
        if fam and k in live_by:
            g.theory(mech_for(fam)).add(experiment=f"live:{k}", supports=live_by[k] > 0,
                                        source="live", context=k)
    rep = g.report()
    return {**rep, "backtest_rows": n_back,
            "metric": {"n_theories": rep["n_theories"], "complete_share":
                       rep["complete_share"], "refuted": rep["by_status"].get("REFUTED", 0),
                       "supported": rep["by_status"].get("SUPPORTED", 0)}}


def organ_review(topo: Mapping[str, Any] | None, fdr_rows: Mapping[str, Any] | None,
                 rq: Mapping[str, Any] | None) -> dict[str, Any]:
    shadow = shadow_rows()
    uniq = ((topo or {}).get("rank") or {}).get("uniqueness") or {}
    over = {r["test_id"]: r for r in (fdr_rows or {}).get("certified") or []}
    rep_doc = _read(REPORTS / "REPLICATION.json") or {}
    # REPLICATION.json (replication_civilization) keeps its rows under "verdicts", keyed "key"
    rep_rows = (rep_doc.get("verdicts") or rep_doc.get("rows") or []) if isinstance(rep_doc,
                                                                                 dict) else []
    rep_by = {}
    for r in rep_rows if isinstance(rep_rows, list) else []:
        if isinstance(r, dict):
            k = str(r.get("cell") or r.get("key") or "")
            v = r.get("verdict") or r.get("status")
            if k:
                rep_by[k] = "AGREE" if str(v).upper() in ("AGREE", "REPLICATED", "PASS",
                                                           "MATCH") else str(v)
    fills: Counter[str] = Counter(str(r.get("sleeve") or "") for r in _jsonl(LIVE_LEDGER))
    cands: dict[str, dict[str, Any]] = {}
    for key, row in survivors().items():
        if not isinstance(row, dict):
            continue
        spec = _spec(row)
        sym, sel, fam = spec.get("symbol"), spec.get("selector"), spec.get("family")
        fw = shadow.get(f"{sym}.{sel}") or {}
        sleeve_keys = [k for k in uniq if str(k).startswith(f"{sym}.{fam}")]
        ev: dict[str, Any] = {"gates": row.get("gates") or {}, "days": row.get("days"),
                              "forward": {"n": fw.get("n"), "mean_r": fw.get("exp_r")},
                              "execution": {"matched_fills": fills.get(f"{sym}.{fam}.{sel}", 0)
                                            + fills.get(str(key), 0)},
                              "mechanism": {"falsifier": ""}}
        if sleeve_keys:
            ev["topology"] = {"uniqueness": uniq[sleeve_keys[0]]}
        if str(key) in over:
            ev["online_fdr"] = {"over_budget": bool(over[str(key)]["over_budget"])}
        cell = str(row.get("cell") or key)
        if cell in rep_by:
            ev["replication"] = {"verdict": rep_by[cell]}
        ev["red_queen"] = None if rq is None else {"attacks": rq.get("generation"),
                                                   "killed": False}
        cands[str(key)] = ev
    rep = review_panel.panel_report(cands)
    rows = rep.pop("rows")
    _write(OUT_DIR / "REVIEW_PANEL_ROWS.json", {"generated_utc": NOW.isoformat(), "rows": rows})
    return {**rep, "metric": {"resolved_share": rep["resolved_share"],
                              "challenged": rep["verdicts"].get("CHALLENGED", 0),
                              "failed": rep["verdicts"].get("FAILED", 0)}}


def organ_market() -> dict[str, Any]:
    """Researchers = factories (hunts / intelligence seats). Their record from the ledgers."""
    rs: dict[str, researcher_market.Researcher] = {}

    def R(name: str) -> researcher_market.Researcher:
        if name not in rs:
            rs[name] = researcher_market.Researcher(name=name, cohort=name.split(":")[0])
        return rs[name]

    hon = _state("honesty").get("factories") or {}
    shadow = shadow_rows()
    for _key, row in survivors().items():
        if not isinstance(row, dict):
            continue
        r = R(str(row.get("hunt") or "unknown"))
        r.successes["full"] = r.successes.get("full", 0) + 1
        spec = _spec(row)
        fw = shadow.get(f"{spec.get('symbol')}.{spec.get('selector')}") or {}
        if fw.get("n") and int(fw["n"]) >= 5:
            r.trials["forward"] = r.trials.get("forward", 0) + 1
            r.successes["forward"] = r.successes.get("forward", 0) + int(
                float(fw.get("exp_r") or 0) > 0)
    judged: Counter[str] = Counter()
    for row in _jsonl(GATE_LEDGER):
        judged[str(row.get("hunt") or row.get("source") or "unknown")] += 1
    for name, n in judged.items():
        r = R(name)
        r.trials["full"] = max(n, r.successes.get("full", 0))
        r.candidates += n
    cpu: Counter[str] = Counter()
    first: dict[str, datetime] = {}
    for row in _jsonl(COMPUTE, 200_000):
        name = str(row.get("run") or "")
        s = row.get("cpu_s") or row.get("wall_s") or row.get("seconds")
        if name and isinstance(s, (int, float)):
            cpu[name] += float(s)
            t = replay.parse_t(row.get("at"))
            if t:
                first[name] = min(first.get(name, t), t)
    for name in list(rs):
        r = rs[name]
        r.cost["cpu_s"] = float(cpu.get(name, 0.0)) or 3600.0
        r.hours = max(1.0, (NOW - first[name]).total_seconds() / 3600.0) if name in first \
            else 24.0
        h = hon.get(name)
        if isinstance(h, dict) and h.get("honesty") is not None:
            r.honesty = float(h["honesty"])
    res = researcher_market.allocate(list(rs.values()), headroom_s=1800.0, seed=NOW.hour)
    sight = []
    for r in _jsonl(HGRAPH, 60_000):
        sight.append((str(r.get("source") or "").split(":")[0], str(r.get("family") or "")))
    ind = researcher_market.independent_discoveries(sight, {})
    _write(STATE / "researcher_prices.json", {"generated_utc": NOW.isoformat(),
                                               "prices": {k: v["price"] for k, v in
                                                          res["allocations"].items()},
                                               "budgets": {k: v["budget_s"] for k, v in
                                                           res["allocations"].items()}})
    return {**res, "independent_discoveries": ind,
            "metric": {"n_researchers": len(rs), "independently_discovered":
                       ind["independently_discovered"]}}


def organ_frontier(topo_hist: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    sightings = []
    for r in _jsonl(HGRAPH, 200_000):
        ground = str(r.get("source") or "?").split(":")[0]
        species = f"{_mechanism(str(r.get('family') or ''))}|{r.get('family')}"
        sightings.append((ground, species))
    comp: dict[str, float] = defaultdict(float)
    for row in _jsonl(COMPUTE, 200_000):
        t = str(row.get("at") or "")[:13]
        s = row.get("cpu_s") or row.get("wall_s") or row.get("seconds")
        if t and isinstance(s, (int, float)):
            comp[t] += float(s)
    surv_by: dict[str, float] = defaultdict(float)
    for row in survivors().values():
        if isinstance(row, dict):
            surv_by[str(row.get("gated_at") or "")[:13]] += 1.0
    hours = sorted(set(comp) | set(surv_by))
    ranks = [float(h["combined"]) for h in (topo_hist or []) if h.get("combined") is not None]
    est = frontier.estimate(sightings, compute_series=[comp.get(h, 0.0) for h in hours],
                            survivor_series=[surv_by.get(h, 0.0) for h in hours],
                            rank_history=ranks)
    return {**est, "metric": {"unseen": est["overall"].get("unseen"),
                              "coverage": est["overall"].get("coverage"),
                              "new_per_100": est["overall"].get("new_per_100_recent"),
                              "yield_b": (est.get("yield") or {}).get("b")}}


def organ_failure_memory() -> dict[str, Any]:
    rows = []
    for r in _jsonl(GATE_LEDGER):
        sym = str(r.get("sym") or "")
        cell = str(r.get("cell") or "")
        parts = cell.split(".")
        rows.append({"family": r.get("family"), "mechanism": _mechanism(str(r.get("family"))),
                     "asset_class": _asset_class(sym) if sym else "?",
                     "selector": parts[2] if len(parts) > 2 else "?",
                     "passed": r.get("passed"), "terminal_gate": r.get("terminal_gate"),
                     "cell": cell})
    mem = failure_memory.compress(rows)
    _write(STATE / "failure_memory.json", {"generated_utc": NOW.isoformat(),
                                            "theorems": mem["theorems"], "rules": mem["rules"]})
    return {**{k: v for k, v in mem.items() if k not in ("theorems", "rules")},
            "theorems": mem["theorems"][:40], "rules": mem["rules"][:20],
            "metric": {"theorems": len(mem["theorems"]),
                       "rows_per_statement": mem["compression"]["rows_per_statement"],
                       "coverage_share": mem["compression"]["coverage_share"]}}


def organ_formal() -> dict[str, Any]:
    abl = formal.ablations()
    existing: dict[str, Any] = {}
    try:
        import formal_invariants as fi  # type: ignore[import-not-found]
        existing = fi.build()
        _write(REPORTS / "FORMAL_INVARIANTS.json", existing)
    except Exception as exc:
        existing = {"error": f"{type(exc).__name__}: {exc}"}
    conformance = _protocol_conformance()
    return {"protocol": {"desk_all_proven": abl["desk_all_proven"],
                         "states": abl["runs"]["desk"]["states"],
                         "invariants": abl["runs"]["desk"]["invariants"],
                         "depends_on": abl["depends_on"]},
            "desk_all_proven": abl["desk_all_proven"],
            "conformance": conformance, "structural_invariants": existing,
            "metric": {"protocol_proven": 1.0 if abl["desk_all_proven"] else 0.0,
                       "knobs_evidenced": conformance.get("evidenced_share")}}


#: protocol knob -> source patterns in the gateway that evidence the real code implements it.
#: Static evidence, not proof; a knob with no evidence is an OBLIGATION the report names.
KNOB_EVIDENCE: dict[str, tuple[str, ...]] = {
    "persist_before_send": ("order_intents", "intent_id", "_journal"),
    "reconcile_on_restart": ("positions_get", "orders_get", "reconcile"),
    "idempotent_client_id": ("magic", "comment", "client_id", "intent_id"),
    "recheck_alloc_at_send": ("allocator gave this sleeve no heat", "book_zeroed", "zeroed"),
    "check_cert_at_send": ("load_sleeves", "live_policy", "admit"),
    "clamp_data_to_clock": ("closed bar", "bar_closed", "iloc[-2]", "last closed"),
}


def _protocol_conformance() -> dict[str, Any]:
    src = ""
    for p in (DESK / "mt5desk" / "gateway.py", DESK / "mt5desk" / "decision_core.py"):
        with contextlib.suppress(OSError):
            src += p.read_text("utf-8", errors="replace")
    if not src:
        return {"status": "UNMEASURED"}
    rows = {k: [pat for pat in pats if pat in src] for k, pats in KNOB_EVIDENCE.items()}
    ev = sum(1 for v in rows.values() if v)
    return {"evidence": rows, "evidenced": ev, "of": len(rows),
            "evidenced_share": ev / len(rows),
            "obligations": [k for k, v in rows.items() if not v]}


def organ_chaos() -> dict[str, Any]:
    camp = chaos.campaign(runs=1500, depth=60, seed=NOW.hour)
    drills = []
    try:
        from mt5desk import decision_core as dc  # type: ignore[import-not-found]
        drills.append(chaos.drill("sleeves.json -> load_sleeves_verbose",
                                  DESK / "data" / "sleeves.json",
                                  lambda p: dc.load_sleeves_verbose(p)[0],
                                  lambda out: out == []))
    except Exception as exc:
        drills.append({"drill": "load_sleeves_verbose", "status": "UNMEASURED",
                       "why": f"{type(exc).__name__}: {exc}"})
    jp = STATE / "truth_journal.jsonl"
    drills.append(chaos.drill("truth journal -> verify", jp,
                              lambda p: truth_kernel.Journal(p).verify(),
                              lambda out: not bool(out.get("ok")) or int(out.get("n", 0)) == 0,
                              corruptions=("truncate", "garbage")))
    failing = [d for d in drills if d.get("status") == "FAIL"]
    return {"campaign": camp, "drills": drills,
            "metric": {"breaches": sum(camp["breaches"].values()),
                       "drills_failing": len(failing)}}


def organ_replay() -> dict[str, Any]:
    streams = [
        replay.Stream("fills", _jsonl(LIVE_LEDGER), "time",
                      key=lambda r: str(r.get("sleeve")), reducer=replay.position_reducer),
        replay.Stream("orders", _jsonl(ORDER_INTENTS), "time",
                      key=lambda r: str(r.get("sleeve")), reducer=replay.count_reducer),
        replay.Stream("decisions", _jsonl(DECISIONS), "decided_at",
                      key=lambda r: str(r.get("strategy_id"))),
        replay.Stream("certificates", [dict(v, _key=k) for k, v in survivors().items()
                                       if isinstance(v, dict)], "gated_at",
                      key=lambda r: str(r.get("_key"))),
        replay.Stream("sleeves", [dict(v, _key=k) for k, v in registry().items()
                                  if isinstance(v, dict)], ("frozen_at", "forward_start"),
                      key=lambda r: str(r.get("_key"))),
        replay.Stream("legs", _jsonl(EVENTS), "at", key=lambda r: str(r.get("leg"))),
        replay.Stream("allocations", _jsonl(FORECAST_LOG), "t", key=lambda r: "book"),
    ]
    live = {"certificates": {str(k) for k in survivors()},
            "sleeves": {str(k) for k in registry()}}
    cons = replay.consistency(streams, live, NOW)
    sample_t = NOW - timedelta(days=7)
    past = replay.replay(streams, sample_t)
    return {**cons, "sample_past": {"at": past["at"],
                                    "sizes": {k: len(v) for k, v in past["state"].items()}},
            "metric": {"reconstructible_share": cons["reconstructible_share"]}}


def organ_data_os() -> dict[str, Any]:
    audits = {}
    for name, p in (("deep_forest_claims", DESK / "data" / "deep_forest_claims.jsonl"),
                    ("news_captures", DESK / "data" / "news_captures.jsonl"),
                    ("hypothesis_graph", HGRAPH)):
        audits[name] = bitemporal.pit_audit(_jsonl(p, 50_000))
    intel_rows: list[dict[str, Any]] = []
    for p in sorted((DESK / "data" / "intelligence").rglob("*.json"))[-400:]:
        d = _read(p)
        rows = d.get("rows") if isinstance(d, dict) else d
        if isinstance(rows, list):
            intel_rows.extend(r for r in rows[:200] if isinstance(r, dict))
    audits["intelligence"] = bitemporal.pit_audit(intel_rows)
    # the acquisition ledger: predictions from the four rankers, resolved on arrival
    st = _state("acquisition")
    preds = [bitemporal.Prediction(**p) for p in st.get("predictions") or []]
    known = {p.item for p in preds}
    metric_now = {"pit_share": float(audits["intelligence"].get("pit_share") or 0.0)}
    for ranker, fname in (("data_acquisition_scientist", "DATA_ACQUISITION.json"),
                          ("evig_acquisition", "EVIG_ACQUISITION.json"),
                          ("source_evig", "SOURCE_EVIG.json"),
                          ("value_of_data", "VALUE_OF_DATA.json")):
        d = _read(REPORTS / fname)
        rows = []
        if isinstance(d, dict):
            for k in ("ranking", "rows", "targets", "candidates", "top"):
                if isinstance(d.get(k), list):
                    rows = d[k]
                    break
        for r in rows[:20]:
            if not isinstance(r, dict):
                continue
            item = str(r.get("item") or r.get("dataset") or r.get("source") or r.get("name")
                       or r.get("id") or "")
            if not item or item in known:
                continue
            gain = r.get("evig") or r.get("value") or r.get("expected_gain") or r.get("score")
            try:
                g = float(gain)
            except (TypeError, ValueError):
                continue
            preds.append(bitemporal.Prediction(item=item, kind=str(r.get("kind") or "dataset"),
                                               ranker=ranker, predicted_gain=g,
                                               cost_eur=float(r.get("cost_eur") or 0.0),
                                               cost_cpu_h=float(r.get("cost_cpu_h") or 0.1),
                                               metric="pit_share",
                                               metric_before=metric_now["pit_share"],
                                               at=NOW.isoformat()))
            known.add(item)
    acquired: dict[str, datetime] = {}
    acq_dir = DESK / "data" / "acquired"
    if acq_dir.exists():
        for p in acq_dir.iterdir():
            acquired[p.stem] = datetime.fromtimestamp(p.stat().st_mtime, UTC)
    n_res = bitemporal.resolve(preds, acquired, metric_now, NOW.isoformat())
    cal = bitemporal.calibration(preds)
    ranking = bitemporal.rank(preds, cal)
    _save_state("acquisition", {"predictions": [p.to_dict() for p in preds][-3000:]})
    return {"pit_audits": audits, "acquisition": {"open": len(ranking),
                                                  "resolved_now": n_res,
                                                  "calibration": cal, "top": ranking[:25]},
            "metric": {"pit_share": audits["intelligence"].get("pit_share"),
                       "calibrated_rankers": len(cal)}}


def organ_world_and_science() -> dict[str, Any]:
    rets, closes, vols = _returns_panel()
    if len(rets) < 3:
        return {"status": "UNMEASURED", "why": f"{len(rets)} eligible H1 series on this host",
                "metric": {"stable_edges": None, "hypotheses": 0}}
    edges = world_edges.classify_all(rets, lags=(1,), max_pairs=300)
    resid = world_edges.residuals(rets, edges)
    labs = cross_science.run_all(rets, closes, vols)
    # map to registered families the compiler can build (the lab stays on the row)
    fam_map = {"control": {"lost": "trend_ma_cross", "over": "mean_reversion_bollinger"},
               "signal": "range_reversion", "queueing": "volatility_squeeze",
               "ecology": "momentum_volgate", "dynamical": "range_reversion",
               "information": "london_close_momentum", "network": "london_close_momentum",
               "bayesian": {"persistence": "trend_ma_cross", "reversion": "mean_reversion_rsi"}}
    rows: list[dict[str, Any]] = []
    for lab, hits in labs.items():
        for h in hits:
            m = fam_map.get(lab)
            if isinstance(m, dict):
                claim = str(h.get("claim"))
                fam = next((v for k, v in m.items() if k in claim), next(iter(m.values())))
            else:
                fam = str(m)
            rows.append({**h, "family": fam, "lab_family": h.get("family"),
                         "text": h.get("claim")})
    for r in resid:
        rows.append({**r, "family": "range_reversion", "text": r.get("claim")})
    emitted = _emit("cross_science", rows)
    census = world_edges.census(edges)
    return {"edges": census, "broken_relationships": resid[:20],
            "labs": {k: len(v) for k, v in labs.items()}, "emitted": emitted,
            "sample": {k: v[:3] for k, v in labs.items()},
            "metric": {"stable_edges": census.get("STABLE", 0), "hypotheses": len(rows)}}


def _posterior_bids() -> tuple[list[opportunity_exchange.Bid], dict[str, float]]:
    shadow = shadow_rows()
    hon = _state("honesty").get("factories") or {}
    live_book: dict[str, float] = {}
    alloc = _first(PF_ALLOCATION)
    if isinstance(alloc, dict) and isinstance(alloc.get("book"), dict):
        live_book = {str(k): float(v) for k, v in alloc["book"].items()}
    bids = []
    for key, row in survivors().items():
        if not isinstance(row, dict):
            continue
        spec = _spec(row)
        k = f"{spec.get('symbol')}.{spec.get('selector')}"
        fw = shadow.get(k) or {}
        n = int(fw.get("n") or 0)
        ev = float(((row.get("gates") or {}).get("expected_value") or {}).get("ev") or 0.0)
        h = float(((hon.get(str(row.get("hunt"))) or {}).get("honesty")) or 1.0)
        prior_mu = ev * h
        mu = prior_mu if n == 0 else (prior_mu * 10 + float(fw.get("exp_r") or 0.0) * n) / (
            10 + n)
        sd = 1.0 / math.sqrt(10 + n)
        bids.append(opportunity_exchange.Bid(
            key=str(key), mu=mu * 0.01, mu_sd=sd * 0.01, sigma=0.01, friction=0.0,
            capacity=0.05, current=float(live_book.get(str(key), 0.0)),
            mechanism=_mechanism(str(spec.get("family") or "")), evidence_arriving=True))
    return bids, live_book


def organ_exchange() -> dict[str, Any]:
    bids, live = _posterior_bids()
    if not bids:
        return {"status": "UNMEASURED", "why": "no certificates on this host",
                "metric": {"defer_share": None}}
    res = opportunity_exchange.clear(bids)
    cmp = opportunity_exchange.compare(res["book"], live, {b.key: b.mu for b in bids})
    _write(STATE / "exchange_book.json", {"generated_utc": NOW.isoformat(), "book": res["book"],
                                          "actions": res["action_counts"]})
    _register_challenger("allocator", "opportunity_exchange", {"k": res["k"]}, None)
    n = sum(res["action_counts"].values())
    return {**{k: v for k, v in res.items() if k != "actions"},
            "actions_sample": dict(list(res["actions"].items())[:30]), "vs_live": cmp,
            "metric": {"expected_log_growth": res["expected_log_growth"],
                       "defer_share": res["action_counts"]["DEFER"] / n if n else None}}


def organ_predictions() -> dict[str, Any]:
    st = _state("forecasts")
    ledger = [prediction_accounting.Forecast(**f) for f in st.get("forecasts") or []]
    shadow = shadow_rows()
    # register this hour's forecast for every LIVE sleeve BEFORE its next outcome
    horizon = (NOW + timedelta(days=2)).isoformat()
    made = 0
    for k, v in registry().items():
        if not isinstance(v, dict) or v.get("status") != "LIVE":
            continue
        idn = v.get("identity") or {}
        fw = shadow.get(f"{idn.get('symbol')}.{idn.get('selector')}") or {}
        n = int(fw.get("n") or 0)
        mu = float(fw.get("exp_r") or 0.0)
        sd = max(0.5, 1.2 / math.sqrt(max(n, 1)) + 0.8)
        try:
            prediction_accounting.register(ledger, prediction_accounting.Forecast(
                key=str(k), made_at=NOW.isoformat(), horizon_end=horizon, mu=mu, sd=sd,
                p_positive=0.5 + 0.5 * math.erf(mu / (sd * math.sqrt(2))),
                source="tier_s.posterior"))
            made += 1
        except prediction_accounting.RegistrationError:
            continue
    outcomes: dict[str, list[tuple[str, float]]] = defaultdict(list)
    traded: list[tuple[str, str]] = []
    for r in _jsonl(LIVE_LEDGER):
        k = str(r.get("sleeve") or "")
        rm = r.get("r_multiple")
        if k and rm is not None and float(rm) != 0.0:
            outcomes[k].append((str(r.get("time")), float(rm)))
        if k:
            traded.append((k, str(r.get("time"))))
    sc = prediction_accounting.score(ledger, outcomes)
    cov = prediction_accounting.unaccounted(traded, ledger)
    # factory honesty: backtest claims vs forward/live
    claims = []
    live_by: dict[str, list[float]] = defaultdict(list)
    for k, v in outcomes.items():
        live_by[k].extend(x for _t, x in v)
    for key, row in survivors().items():
        if not isinstance(row, dict):
            continue
        spec = _spec(row)
        fw = shadow.get(f"{spec.get('symbol')}.{spec.get('selector')}") or {}
        ev = float(((row.get("gates") or {}).get("expected_value") or {}).get("ev") or 0.0)
        lk = [x for s, xs in live_by.items() if s.startswith(f"{spec.get('symbol')}.")
              for x in xs]
        claims.append(prediction_accounting.Claim(
            factory=str(row.get("hunt") or "unknown"), key=str(key), claimed_edge=ev,
            forward_edge=float(fw["exp_r"]) if fw.get("exp_r") is not None else None,
            forward_n=int(fw.get("n") or 0),
            live_edge=(sum(lk) / len(lk)) if lk else None, live_n=len(lk)))
    hon = prediction_accounting.honesty(claims)
    _save_state("honesty", hon)
    cutoff = (NOW - timedelta(days=30)).isoformat()
    _save_state("forecasts", {"forecasts": [f.__dict__ for f in ledger
                                            if f.made_at >= cutoff][-20_000:]})
    return {"registered_now": made, "score": sc, "coverage": cov, "honesty": hon,
            "metric": {"crps": sc["crps"], "coverage90": sc["coverage90"],
                       "accounted_share": cov["accounted_share"],
                       "overconfidence": sc["overconfidence"]}}


def _register_challenger(component: str, name: str, genome: Any,
                         fitness: Any) -> None:
    st = _state("challengers")
    rows = {r["name"]: r for r in st.get("challengers") or []}
    if name not in rows:
        rows[name] = {"component": component, "name": name,
                      "registered_at": NOW.isoformat(),
                      "genome_hash": truth_kernel.sha256(truth_kernel.canon(genome))[:16],
                      "genome": genome, "fitness": fitness}
    _save_state("challengers", {"challengers": list(rows.values())[-200:]})


def organ_twin(sealed_now: Mapping[str, Any]) -> dict[str, Any]:
    st = _state("challengers")
    out = []
    ex = _read(STATE / "exchange_book.json") or {}
    daily: dict[str, dict[str, float]] = defaultdict(dict)
    for r in _jsonl(LIVE_LEDGER):
        daily[str(r.get("time"))[:10]][str(r.get("sleeve"))] = daily[str(r.get("time"))[:10]]\
            .get(str(r.get("sleeve")), 0.0) + float(r.get("r_multiple") or 0.0)
    live_hist = _jsonl(FORECAST_LOG, 50_000)
    live_book_by_day = {str(r.get("t"))[:10]: r.get("book") or {} for r in live_hist}
    for c in st.get("challengers") or []:
        ch = twin.Challenger(c["component"], c["name"], c["registered_at"], c["genome_hash"])
        pairs = []
        if c["component"] == "allocator":
            book = ex.get("book") or {}
            for day, pnl in sorted(daily.items()):
                lb = live_book_by_day.get(day) or {}
                inc = sum(float(lb.get(k, 0.0)) * v for k, v in pnl.items())
                cha = sum(float(book.get(k, 0.0)) * v for k, v in pnl.items())
                pairs.append((f"{day}T23:59:59+00:00", inc, cha))
        res = twin.evaluate(ch, pairs)
        adoption = self_model.adoption(c, res["verdict"], res["money_path"],
                                       bool(sealed_now.get("blocked")))
        if adoption == "ADOPTED" and c["component"] == "validator" and isinstance(
                c.get("genome"), dict):
            ad = _state("adopted")
            ad["validator"] = c["genome"]
            ad["validator_adopted_at"] = NOW.isoformat()
            _save_state("adopted", ad)
        out.append({"name": c["name"], "component": c["component"], **res,
                    "adoption": adoption})
    # validator challengers are judged on the SEALED suite, not on pairs
    for row in out:
        if row["component"] != "validator":
            continue
        c = next(x for x in st.get("challengers") or [] if x["name"] == row["name"])
        fit = c.get("fitness") or {}
        imm = _state("immune").get("history") or [{}]
        inc_bal = ((imm[-1].get("immune_score") or 0) + (imm[-1].get("power") or 0)) / 2
        if isinstance(fit, dict) and fit.get("balanced") is not None:
            better = float(fit["balanced"]) > inc_bal + 0.01
            row["sealed_balanced"] = fit["balanced"]
            row["incumbent_balanced"] = inc_bal
            if better and not sealed_now.get("blocked"):
                row["adoption"] = "ADOPTED"
                ad = _state("adopted")
                ad["validator"] = c.get("genome")
                ad["validator_adopted_at"] = NOW.isoformat()
                ad["validator_from"] = c["name"]
                _save_state("adopted", ad)
    rb = twin.rollback_plan(_release_history())
    return {"challengers": out[-30:], "rollback": rb,
            "metric": {"challengers": len(out),
                       "adopted": sum(1 for r in out if r["adoption"] == "ADOPTED")}}


def _release_history() -> list[dict[str, Any]]:
    """Distinct sealed code SHAs, oldest first: the immutable manifest's `code`, then the
    current RELEASE.json `code_sha` if it is newer than the manifest's last."""
    rows: list[dict[str, Any]] = []
    for r in _jsonl(DESK / "data" / "LIVE_MANIFEST.jsonl", 20_000):
        sha = r.get("code") or r.get("sha") or r.get("code_sha")
        if sha and (not rows or rows[-1]["sha"] != str(sha)):
            rows.append({"sha": str(sha), "at": r.get("at"), "sealed": True})
    rel = _read(DESK / "data" / "RELEASE.json") or {}
    sha = rel.get("code_sha") or rel.get("live_sha")
    if sha and (not rows or rows[-1]["sha"] != str(sha)):
        rows.append({"sha": str(sha), "at": rel.get("generated_utc"), "sealed": True})
    return rows


# ------------------------------------------------------------------------------------------------
# contracts, epistemics, self-model
# ------------------------------------------------------------------------------------------------

def evaluate_contracts(reports: Mapping[str, Any]) -> dict[str, Any]:
    ledger = _read(LEDGER) or {}
    st = _state("contracts")
    hist: dict[str, list[float]] = {k: list(v) for k, v in (st.get("history") or {}).items()}
    out: dict[str, Any] = {}
    counts: Counter[str] = Counter()
    for layer in ledger.get("layers") or []:
        lid = str(layer.get("id"))
        raw = layer.get("contract") or {}
        try:
            c = contracts.Contract.parse(raw)
        except (KeyError, ValueError) as exc:
            out[lid] = {"verdict": "INVALID", "why": str(exc)}
            counts["INVALID"] += 1
            continue
        organ = str(raw.get("organ") or "")
        if organ.startswith("report:"):
            # a layer whose organ is an existing desk leg: read that leg's own artifact
            src = _read(DESK / "reports" / organ.split(":", 1)[1]) or {}
        else:
            src = reports.get(organ) or {}
        val = contracts.read_metric(src, c.metric)
        if val is not None:
            hist.setdefault(lid, []).append(val)
            hist[lid] = hist[lid][-500:]
        ev = contracts.evaluate(c, hist.get(lid, []))
        out[lid] = {**ev, "gain": str(c.gain), "metric": f"{organ}.{c.metric}",
                    "latest": val}
        counts[ev["verdict"]] += 1
    _save_state("contracts", {"history": hist})
    return {"layers": out, "counts": dict(counts)}


def epistemic_census(reports: Mapping[str, Any]) -> dict[str, Any]:
    qs: list[epistemic.Quantity] = []
    imm = (reports.get("immune") or {}).get("score") or {}
    if imm.get("n_cases"):
        n_traps = sum(v["n"] for k, v in (imm.get("per_kind") or {}).items()
                      if not k.startswith("true"))
        rej = round((imm.get("immune_score") or 0) * n_traps)
        qs.append(epistemic.beta_quantity("immune_score", int(rej), int(n_traps),
                                          source="immune"))
    pa = reports.get("predictions") or {}
    cov = (pa.get("coverage") or {})
    if cov.get("trades"):
        acc = int(cov["trades"]) - int(cov["unaccounted"])
        qs.append(epistemic.beta_quantity("accounted_share", acc, int(cov["trades"]),
                                          source="predictions"))
    for key, row in list(survivors().items())[:500]:
        if not isinstance(row, dict):
            continue
        spec = _spec(row)
        fw = shadow_rows().get(f"{spec.get('symbol')}.{spec.get('selector')}") or {}
        n = int(fw.get("n") or 0)
        t = fw.get("forward_t")
        if n and t is not None and fw.get("exp_r") is not None:
            mu = float(fw["exp_r"])
            se = abs(mu / float(t)) if float(t) != 0 else None
            qs.append(epistemic.Quantity(f"forward_edge:{key}", mu,
                                         None if se is None else mu - 1.96 * se,
                                         None if se is None else mu + 1.96 * se, n=n,
                                         source="shadow"))
        else:
            qs.append(epistemic.Quantity(f"forward_edge:{key}", None, n=0, source="shadow"))
    cen = epistemic.census(qs, {q.name: 0.0 for q in qs if q.name.startswith("forward_edge")})
    undecided = sum(1 for q in qs if q.name.startswith("forward_edge") and
                    epistemic.decide(q, 0.0) == epistemic.Decision.INSUFFICIENT_EVIDENCE)
    return {**cen, "forward_edges_undecided": undecided,
            "statement": f"{undecided} certificates' forward edge cannot yet be decided from "
                         "their evidence -- there is not enough evidence to decide them",
            "metric": {"decidable_share": cen["decidable_share"]}}


def organ_self_model(reports: dict[str, Any]) -> dict[str, Any]:
    card = self_model.sealed_scorecard(reports)
    st = _state("self_model")
    prev = st.get("scorecard") or {}
    reg = self_model.regression(prev, card)
    defs = self_model.rank(self_model.inventory(reports))
    best = st.get("best") or {}
    for k, better in self_model.SEALED_METRICS.items():
        v = card.get(k)
        if v is None:
            continue
        if k not in best or (better == "up" and v > best[k]) or (better == "down"
                                                                 and v < best[k]):
            best[k] = v
    _save_state("self_model", {"scorecard": card, "best": best, "at": NOW.isoformat()})
    docket = [{"task": f"Tier S deficiency: {d['area']}", "why": d["why"],
               "expected_improvement": d["expected_improvement"], "gain": d["gain"]}
              for d in defs[:10]]
    _write(STATE / "SELF_MODEL_DOCKET.json", {"generated_utc": NOW.isoformat(),
                                               "tasks": docket})
    return {"scorecard": card, "best_ever": best, "regression": reg,
            "largest_deficiency": defs[0] if defs else None, "deficiencies": defs[:25],
            "metric": {"top_expected_improvement": defs[0]["expected_improvement"] if defs
                       else None, "regressed": len(reg["regressed"])}}


# ------------------------------------------------------------------------------------------------
# main
# ------------------------------------------------------------------------------------------------

def _run(name: str, fn: Callable[[], dict[str, Any]], timings: dict[str, float],
         errors: dict[str, str]) -> dict[str, Any]:
    t0 = time.perf_counter()
    try:
        out = fn()
    except Exception as exc:
        errors[name] = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()[-1200:]}"
        out = {"status": "ERROR", "error": errors[name][:400]}
    timings[name] = round(time.perf_counter() - t0, 3)
    out.setdefault("generated_utc", NOW.isoformat())
    out["seconds"] = timings[name]
    _write(OUT_DIR / f"{name.upper()}.json", out)
    print(f"tier_s {name}: {timings[name]:.1f}s"
          + (f" ERROR {errors[name].splitlines()[0]}" if name in errors else ""), flush=True)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--only", default="", help="comma-separated organ names")
    ap.add_argument("--dry-run", action="store_true", help="probation: run the fast organs only")
    ap.add_argument("--rollback-to", default=None,
                    help="print the one-commit rollback plan to this sealed release")
    ap.add_argument("--apply-rollback", action="store_true",
                    help="with --rollback-to: make that one commit (never pushes)")
    a = ap.parse_args(argv)
    if a.rollback_to:
        from libs.tiers import rollback
        plan = rollback.plan(a.rollback_to)
        print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in plan.items()},
                         indent=1))
        if not plan.get("available"):
            return 1
        if a.apply_rollback:
            if not plan.get("sealed"):
                print("refusing: the target is not a sealed release in LIVE_MANIFEST")
                return 1
            print(f"rolled back in one commit: {rollback.apply(plan)}")
        return 0
    only = {x.strip() for x in a.only.split(",") if x.strip()}
    if a.dry_run:
        only = only or {"formal", "firewall", "epistemic"}
    timings: dict[str, float] = {}
    errors: dict[str, str] = {}
    reports: dict[str, Any] = {}

    def want(n: str) -> bool:
        return not only or n in only

    plan: list[tuple[str, Callable[[], dict[str, Any]]]] = [
        ("truth_kernel", organ_truth_kernel), ("firewall", organ_firewall),
        ("immune", organ_immune), ("red_queen", organ_red_queen),
        ("test_invention", organ_test_invention), ("online_fdr", organ_online_fdr),
        ("topology", organ_topology), ("qd", organ_qd), ("genomes", organ_genomes),
        ("grammar", organ_grammar), ("theory", organ_theory),
        ("predictions", organ_predictions), ("market", organ_market),
        ("failure_memory", organ_failure_memory), ("formal", organ_formal),
        ("chaos", organ_chaos), ("replay", organ_replay), ("data_os", organ_data_os),
        ("world_science", organ_world_and_science), ("exchange", organ_exchange),
    ]
    for name, fn in plan:
        if want(name):
            reports[name] = _run(name, fn, timings, errors)
    if want("frontier"):
        th = _state("topology").get("rank_history") or []
        reports["frontier"] = _run("frontier", lambda: organ_frontier(th), timings, errors)
    if want("review"):
        fdr_rows = _read(OUT_DIR / "ONLINE_FDR_ROWS.json")
        reports["review"] = _run("review", lambda: organ_review(
            reports.get("topology"), fdr_rows, reports.get("red_queen")), timings, errors)
    if want("epistemic"):
        reports["epistemic"] = _run("epistemic", lambda: epistemic_census(reports), timings,
                                    errors)
    if want("contracts") or not only:
        reports["contracts"] = _run("contracts", lambda: evaluate_contracts(reports), timings,
                                    errors)
    if want("self_model"):
        reports["self_model"] = _run("self_model", lambda: organ_self_model(reports), timings,
                                     errors)
    if want("twin"):
        sm = reports.get("self_model") or {}
        reports["twin"] = _run("twin", lambda: organ_twin(sm.get("regression") or {}),
                               timings, errors)
    summary = {"generated_utc": NOW.isoformat(), "organs": sorted(reports),
               "seconds": timings, "total_seconds": round(sum(timings.values()), 2),
               "errors": {k: v.splitlines()[0] for k, v in errors.items()},
               "metrics": {k: (v or {}).get("metric") for k, v in reports.items()},
               "contracts": (reports.get("contracts") or {}).get("counts"),
               "largest_deficiency": ((reports.get("self_model") or {})
                                      .get("largest_deficiency")),
               "immune_verdict": ((reports.get("immune") or {}).get("verdict")),
               "emitted": {k: (v or {}).get("emitted") for k, v in reports.items()
                           if isinstance(v, dict) and v.get("emitted")}}
    if not only:
        _write(SUMMARY, summary)
    print(json.dumps({"total_seconds": summary["total_seconds"],
                      "errors": list(summary["errors"])}), flush=True)
    return 1 if errors and len(errors) == len(timings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
